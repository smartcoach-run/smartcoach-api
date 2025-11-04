from flask import Flask, request, jsonify
from pyairtable import Api
import os
from datetime import datetime

app = Flask(__name__)

# ========= ENV VARS =========
AIRTABLE_KEY = os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("BASE_ID")

TABLE_COUR_NAME = os.environ.get("TABLE_COUR")                 # 🏃 Coureurs
TABLE_SEANCES_NAME = os.environ.get("TABLE_SEANCES")           # 🏋️ Séances   (générées)
TABLE_SEANCES_TYPES_NAME = os.environ.get("TABLE_SEANCES_TYPES")  # 📘 Séances types (référentiel)

# Validation ENV
missing_env = [k for k, v in {
    "AIRTABLE_KEY": AIRTABLE_KEY,
    "BASE_ID": BASE_ID,
    "TABLE_COUR": TABLE_COUR_NAME,
    "TABLE_SEANCES": TABLE_SEANCES_NAME,
    "TABLE_SEANCES_TYPES": TABLE_SEANCES_TYPES_NAME
}.items() if not v]

if missing_env:
    raise RuntimeError(f"[CONFIG] Variables d’environnement manquantes: {', '.join(missing_env)}")

# ========= AIRTABLE CLIENTS =========
api = Api(AIRTABLE_KEY)
TABLE_COUR = api.table(BASE_ID, TABLE_COUR_NAME)
TABLE_SEANCES = api.table(BASE_ID, TABLE_SEANCES_NAME)                 # 🏋️ Séances (écriture)
TABLE_SEANCES_TYPES = api.table(BASE_ID, TABLE_SEANCES_TYPES_NAME)     # 📘 Séances types (lecture)

def weeks_between(d1, d2):
    """Nombre de semaines arrondi, min=1."""
    try:
        return max(1, round((d2 - d1).days / 7))
    except Exception:
        return 8  # fallback

def verifier_jours(fields):
    """
    Ajuste le nb de jours hebdo selon RG B03-COH (Jours_min/Jours_max du réf niveaux).
    Entrées (côté Coureurs) :
      - 📅Nb_jours_dispo (nombre)
      - Jours_min, Jours_max (nombres déjà injectés depuis le référentiel)
    Sortie : int jours_final
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

@app.get("/")
def health():
    return "SmartCoach API active ✅"

@app.post("/generate_by_id")
def generate_by_id():
    """
    Scénario 1 :
      - Lit le coureur
      - Calcule nb_semaines = (date_objectif - today) en semaines
      - Sélectionne des séances dans 📘 Séances types (filtre Mode/Phase/Niveau/Objectif/VDOT)
      - Écrit dans 🏋️ Séances (Coureur link + champs copiés)
    """
    data = request.json or {}
    record_id = data.get("id")

    # Sécurité entrée
    if not record_id:
        return jsonify({
            "status": "error",
            "message_id": "SC_API_001",
            "message": "⚠️ Aucun ID de coureur reçu dans la requête.",
            "expected_format": {"id": "recXXXXXXXXXXXXXX"}
        }), 400

    # Récup coureur
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

    # Nb de semaines via date objectif
    nb_semaines = 8
    date_obj = fields.get("Date_objectif")
    if date_obj:
        try:
            # Airtable retourne souvent en ISO avec Z → on normalise
            d_obj = datetime.fromisoformat(date_obj.replace("Z","").replace("z",""))
            nb_semaines = weeks_between(datetime.today(), d_obj)
        except Exception:
            pass

    # Nb de jours hebdo (RG B03-COH)
    jours_final = verifier_jours(fields)

    # Phases de début de plan (pré-gén & progression)
    PHASES_AUTORISEES = ["Prépa générale", "Progression"]

    # Récup référentiel des séances types
    try:
        all_seances_types = TABLE_SEANCES_TYPES.all()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message_id": "SC_API_003",
            "message": f"❌ Impossible de lire 📘 Séances types: {e}"
        }), 500

    # Filtrage multi-critères
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

        # OK → candidate
        seances_valides.append(f)

    if not seances_valides:
        return jsonify({
            "status": "error",
            "message_id": "SC_COACH_012",
            "message": "Aucune séance adaptée trouvée. Référentiel à compléter.",
            "seances": []
        }), 200

    # Tri progressivité (Charge puis Durée)
    seances_valides = sorted(
        seances_valides,
        key=lambda x: (x.get("Charge", 2), x.get("Durée (min)", 30))
    )

    # Construction du plan + écriture dans 🏋️ Séances
    total_crees = 0
    sorties = []

    for semaine in range(1, nb_semaines + 1):
        bloc = seances_valides[:max(1, jours_final)]
        for j, f in enumerate(bloc, start=1):
            payload = {
                # table cible 🏋️ Séances
                "Coureur": [record_id],                        # link
                "NomSéance": f.get("Nom séance"),              # depuis 📘 Séances types
                "Phase": f.get("Phase"),
                "Type": f.get("Type"),
                "Durée (min)": f.get("Durée (min)"),
                "Charge": f.get("Charge", 2),
                "🧠 Message_coach": f.get("🧠 Message_coach (modèle)"),
                "Semaine": semaine,
                "Jour planifié": j
            }
            # Création Airtable
            TABLE_SEANCES.create(payload)
            total_crees += 1
            sorties.append(payload)

    return jsonify({
        "status": "ok",
        "message_id": "SC_COACH_021",
        "message": f"✅ {total_crees} séances générées ({nb_semaines} sem × {jours_final}/sem).",
        "nb_semaines": nb_semaines,
        "jours_par_semaine": jours_final,
        "total": total_crees
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)