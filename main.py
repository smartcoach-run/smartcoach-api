import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from pyairtable import Api
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ========= ENV VARS =========
AIRTABLE_KEY = os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("BASE_ID")

TABLE_COUR_NAME = os.environ.get("TABLE_COUR")                   # 🏃 Coureurs
TABLE_SEANCES_NAME = os.environ.get("TABLE_SEANCES")             # 🏋️ Séances (générées)
TABLE_SEANCES_TYPES_NAME = os.environ.get("TABLE_SEANCES_TYPES") # 📘 Séances types (référentiel)
TABLE_ARCHIVES_NAME = os.environ.get("TABLE_ARCHIVES")           # 🗄️ Archives Séances

# Validation ENV
missing_env = [k for k, v in {
    "AIRTABLE_KEY": AIRTABLE_KEY,
    "BASE_ID": BASE_ID,
    "TABLE_COUR": TABLE_COUR_NAME,
    "TABLE_SEANCES": TABLE_SEANCES_NAME,
    "TABLE_SEANCES_TYPES": TABLE_SEANCES_TYPES_NAME,
    "TABLE_ARCHIVES": TABLE_ARCHIVES_NAME
}.items() if not v]

if missing_env:
    raise RuntimeError(f"[CONFIG] Variables d’environnement manquantes: {', '.join(missing_env)}")

# ========= AIRTABLE CLIENTS =========
api = Api(AIRTABLE_KEY)
TABLE_COUR = api.table(BASE_ID, TABLE_COUR_NAME)
TABLE_SEANCES = api.table(BASE_ID, TABLE_SEANCES_NAME)                 # 🏋️ Séances (écriture)
TABLE_SEANCES_TYPES = api.table(BASE_ID, TABLE_SEANCES_TYPES_NAME)     # 📘 Séances types (lecture)
TABLE_ARCHIVES = api.table(BASE_ID, TABLE_ARCHIVES_NAME)               # 🗄️ Archives (écriture)

# ========= HELPERS =========
def weeks_between(d1, d2):
    """Nombre de semaines arrondi, min=1."""
    try:
        return max(1, round((d2 - d1).days / 7))
    except Exception:
        return 8  # fallback

def verifier_jours(fields):
    """
    Ajuste le nb de jours hebdo selon RG B03-COH (Jours_min/Jours_max du réf niveaux).
    """
    jours_dispo = fields.get("📅Nb_jours_dispo")
    try:
        jours_dispo = int(jours_dispo)
    except Exception:
        jours_dispo = 1

    jmin = fields.get("Jours_min")
    jmax = fields.get("Jours_max")
    try:
        jmin = int(jmin) if jmin is not None else None
        jmax = int(jmax) if jmax is not None else None
    except Exception:
        jmin, jmax = None, None

    if jmin is None or jmax is None:
        return max(1, jours_dispo)

    return max(jmin, min(jours_dispo, jmax))

def _filter_formula_sessions_for_coureur(record_id: str) -> str:
    """
    Filtre robuste pour récupérer les séances liées à un coureur (champ Link).
    Utilise SEARCH sur ARRAYJOIN pour éviter les égalités sur array.
    """
    return f"SEARCH('{record_id}', ARRAYJOIN({{Coureur}}))"

# ========= ROUTES =========
@app.get("/")
def health():
    return "SmartCoach API active ✅"

@app.post("/generate_by_id")
def generate_by_id():
    data = request.json or {}
    record_id = data.get("id")

    if not record_id:
        return jsonify({
            "status": "error",
            "message_id": "SC_API_001",
            "message": "⚠️ Aucun ID reçu.",
            "expected_format": {"id": "recXXXXXXXXXXXXXX"}
        }), 400

    try:
        rec = TABLE_COUR.get(record_id)
    except Exception as e:
        return jsonify({
            "status": "error",
            "message_id": "SC_API_002",
            "message": f"❌ Coureur introuvable: {e}"
        }), 404

    fields = rec.get("fields", {})
    niveau = fields.get("Niveau_normalisé")
    objectif = fields.get("Objectif_normalisé")
    vdot = fields.get("VDOT_utilisé")

    # Nb semaines (calcul date)
    nb_semaines = 8
    date_obj = fields.get("Date_objectif")
    if date_obj:
        try:
            d_obj = datetime.fromisoformat(date_obj.replace("Z", "").replace("z", ""))
            nb_semaines = weeks_between(datetime.today(), d_obj)
        except Exception:
            pass

    # Jours hebdo
    jours_final = verifier_jours(fields)

    # Phases autorisées début de plan
    PHASES_AUTORISEES = ["Prépa générale", "Progression"]

    # Référentiel séances types
    try:
        all_seances_types = TABLE_SEANCES_TYPES.all()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message_id": "SC_API_003",
            "message": f"❌ Impossible de lire 📘 Séances types: {e}"
        }), 500

    # Filtrage référentiel
    seances_valides = []
    for s in all_seances_types:
        f = s.get("fields", {})

        # 1) Mode
        if f.get("Mode") != "Running":
            continue

        # 2) Phase
        if f.get("Phase") not in PHASES_AUTORISEES:
            continue

        # 3) Niveau (multi-select)
        niveaux = f.get("Niveau") or []
        if isinstance(niveaux, str):
            niveaux = [niveaux]
        if niveau and (niveau not in niveaux):
            continue

        # 4) Objectif (multi-select)
        objectifs = f.get("Objectif") or []
        if isinstance(objectifs, str):
            objectifs = [objectifs]
        if objectif and (objectif not in objectifs):
            continue

        # 5) Fenêtre VDOT
        vmin = f.get("VDOT_min")
        vmax = f.get("VDOT_max")
        try:
            if vmin is not None and vmax is not None and vdot is not None:
                dv = float(vdot)
                if not (float(vmin) <= dv <= float(vmax)):
                    continue
        except Exception:
            pass

        # Candidate
        seances_valides.append(f)

    if not seances_valides:
        return jsonify({
            "status": "error",
            "message_id": "SC_COACH_012",
            "message": "Aucune séance adaptée trouvée dans le référentiel."
        }), 200

    # Tri progressivité (Charge puis Durée)
    seances_valides = sorted(
        seances_valides,
        key=lambda x: (x.get("Charge", 2), x.get("Durée (min)", 30))
    )

    # === B06-SEANCES-04 : Archivage avant régénération ===
    # On regarde s'il existe déjà des séances pour ce coureur
    existing = TABLE_SEANCES.all(formula=_filter_formula_sessions_for_coureur(record_id))
    had_existing = len(existing) > 0

    if had_existing:
        try:
            # 1) Archiver chaque séance existante
            for s in existing:
                f = s.get("fields", {})
                archive_payload = {
                    "Coureur": [record_id],
                    "ID_Seance_Originale": s.get("id"),
                    "Nom séance": f.get("Nom séance"),
                    "Type séance": f.get("Type"),  # dans 🏋️ Séances, Type est texte simple
                    "Durée (min)": f.get("Durée (min)"),
                    "Allure / zone": f.get("Allure / zone"),
                    "Charge": f.get("Charge"),
                    "Détails JSON": json.dumps(f, ensure_ascii=False),
                    "Version plan": fields.get("Version_plan", "v1"),
                    "Source": "Nouvelle demande"
                }
                TABLE_ARCHIVES.create(archive_payload)

            # 2) Supprimer ensuite toutes les séances existantes
            for s in existing:
                TABLE_SEANCES.delete(s["id"])
        except Exception as e:
            return jsonify({
                "status": "error",
                "message_id": "SC_COACH_025",
                "message": f"⚠️ Erreur lors de l'archivage du plan existant : {e}"
            }), 500

    # === Génération du nouveau plan ===
    total_crees = 0
    sorties = []

    for semaine in range(1, nb_semaines + 1):
        bloc = seances_valides[:max(1, jours_final)]
        for j, f in enumerate(bloc, start=1):
            # Conversion : Type séance (multi-select côté référentiel) → texte (champ Type)
            type_brut = f.get("Type séance")
            if isinstance(type_brut, list) and len(type_brut) > 0:
                type_final = type_brut[0]
            else:
                type_final = type_brut if isinstance(type_brut, str) else None

            payload = {
                "Coureur": [record_id],
                "Nom séance": f.get("Nom séance"),
                "Clé séance": f.get("Clé séance"),
                "Type": type_final,
                "Phase": f.get("Phase"),
                "Durée (min)": f.get("Durée (min)"),
                "Charge": f.get("Charge", 2),
                "🧠 Message_coach": f.get("🧠 Message_coach (modèle)"),
                "Semaine": semaine,
                "Jour planifié": j
            }

            TABLE_SEANCES.create(payload)
            total_crees += 1
            sorties.append(payload)

    # Message final selon le cas
    if had_existing:
        return jsonify({
            "status": "ok",
            "message_id": "SC_COACH_023",
            "message": f"🔁 Plan mis à jour : anciennes séances archivées puis {total_crees} recréées ({nb_semaines} sem × {jours_final}/sem).",
            "nb_semaines": nb_semaines,
            "jours_par_semaine": jours_final,
            "total": total_crees
        }), 200
    else:
        return jsonify({
            "status": "ok",
            "message_id": "SC_COACH_024",
            "message": f"✅ {total_crees} séances générées ({nb_semaines} sem × {jours_final}/sem).",
            "nb_semaines": nb_semaines,
            "jours_par_semaine": jours_final,
            "total": total_crees
        }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)