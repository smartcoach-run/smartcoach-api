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

TABLE_COUR_NAME = os.environ.get("TABLE_COUR")
TABLE_SEANCES_NAME = os.environ.get("TABLE_SEANCES")
TABLE_SEANCES_TYPES_NAME = os.environ.get("TABLE_SEANCES_TYPES")
TABLE_ARCHIVES_NAME = os.environ.get("TABLE_ARCHIVES")

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

api = Api(AIRTABLE_KEY)
TABLE_COUR = api.table(BASE_ID, TABLE_COUR_NAME)
TABLE_SEANCES = api.table(BASE_ID, TABLE_SEANCES_NAME)
TABLE_SEANCES_TYPES = api.table(BASE_ID, TABLE_SEANCES_TYPES_NAME)
TABLE_ARCHIVES = api.table(BASE_ID, TABLE_ARCHIVES_NAME)

def weeks_between(d1, d2):
    try:
        return max(1, round((d2 - d1).days / 7))
    except:
        return 8

def verifier_jours(fields):
    jours_dispo = fields.get("📅Nb_jours_dispo")
    try:
        jours_dispo = int(jours_dispo)
    except:
        jours_dispo = 1

    jmin = fields.get("Jours_min")
    jmax = fields.get("Jours_max")
    try:
        jmin = int(jmin) if jmin is not None else None
        jmax = int(jmax) if jmax is not None else None
    except:
        jmin, jmax = None, None

    if jmin is None or jmax is None:
        return max(1, jours_dispo)

    return max(jmin, min(jours_dispo, jmax))

def _filter_formula_sessions_for_coureur(record_id: str) -> str:
    return f"SEARCH('{record_id}', ARRAYJOIN({{Coureur}}))"

@app.get("/")
def health():
    return "SmartCoach API active ✅"

@app.post("/generate_by_id")
def generate_by_id():
    data = request.json or {}
    record_id = data.get("id")

    if not record_id:
        return jsonify({"status": "error", "message_id": "SC_API_001", "message": "⚠️ Aucun ID reçu."}), 400

    try:
        rec = TABLE_COUR.get(record_id)
    except Exception as e:
        return jsonify({"status": "error", "message_id": "SC_API_002", "message": f"❌ Coureur introuvable: {e}"}), 404

    fields = rec.get("fields", {})
    niveau = fields.get("Niveau_normalisé")
    objectif = fields.get("Objectif_normalisé")
    vdot = fields.get("VDOT_utilisé")

    nb_semaines = 8
    date_obj = fields.get("Date_objectif")
    if date_obj:
        try:
            d_obj = datetime.fromisoformat(date_obj.replace("Z",""))
            nb_semaines = weeks_between(datetime.today(), d_obj)
        except:
            pass

    jours_final = verifier_jours(fields)

    PHASES_AUTORISEES = ["Prépa générale", "Progression"]

    try:
        all_seances_types = TABLE_SEANCES_TYPES.all()
    except Exception as e:
        return jsonify({"status":"error","message_id":"SC_API_003","message":f"❌ Impossible de lire référentiel: {e}"}), 500

    seances_valides = []
    for s in all_seances_types:
        f = s.get("fields", {})

        if f.get("Mode") != "Running":
            continue
        if f.get("Phase") not in PHASES_AUTORISEES:
            continue

        niveaux = f.get("Niveau") or []
        if isinstance(niveaux, str): niveaux = [niveaux]
        if niveau and niveau not in niveaux:
            continue

        objectifs = f.get("Objectif") or []
        if isinstance(objectifs, str): objectifs = [objectifs]
        if objectif and objectif not in objectifs:
            continue

        vmin = f.get("VDOT_min")
        vmax = f.get("VDOT_max")
        try:
            if vmin is not None and vmax is not None and vdot is not None:
                dv = float(vdot)
                if not (float(vmin) <= dv <= float(vmax)):
                    continue
        except:
            pass

        seances_valides.append(f)

    if not seances_valides:
        return jsonify({"status":"error","message_id":"SC_COACH_012","message":"Aucune séance adaptée trouvée."}), 200

    seances_valides = sorted(seances_valides, key=lambda x:(x.get("Charge",2),x.get("Durée (min)",30)))

    # === ARCHIVAGE ===
    filter_sessions = _filter_formula_sessions_for_coureur(record_id)
    existing = TABLE_SEANCES.all(formula=filter_sessions)
    had_existing = len(existing) > 0

    if had_existing:
        for s in existing:
            f = s.get("fields", {})

            TABLE_ARCHIVES.create({
                "ID séance originale": s["id"],
                "Coureur": [record_id],
                "Nom séance": f.get("Nom séance"),
                "Type séance": f.get("Type séance") or f.get("Type"),
                "Durée (min)": f.get("Durée (min)"),
                "Allure / zone": f.get("Allure / zone"),
                "Charge": f.get("Charge"),
                "Détails JSON": json.dumps(f, ensure_ascii=False),
                "Version plan": fields.get("Version_plan", "v1"),
                "Date archivage": datetime.utcnow().isoformat(),
                "Source": "Mise à jour"
            })

        for s in existing:
            TABLE_SEANCES.delete(s["id"])

    # === GÉNÉRATION ===
    total_crees = 0
    for semaine in range(1, nb_semaines+1):
        bloc = seances_valides[:max(1, jours_final)]
        for j, f in enumerate(bloc, start=1):

            # Récupération robuste du type
            type_brut = f.get("Type séance") or f.get("Type")
            type_final = type_brut[0] if isinstance(type_brut, list) else type_brut

            TABLE_SEANCES.create({
                "Coureur": [record_id],
                "Nom séance": f.get("Nom séance"),
                "Clé séance": f.get("Clé séance"),
                "Phase": f.get("Phase"),
                "Type séance": type_final,  # ✅ Champ correct
                "Durée (min)": f.get("Durée (min)"),
                "Charge": f.get("Charge", 2),
                "🧠 Message_coach": f.get("🧠 Message_coach (modèle)"),
                "Semaine": semaine,
                "Jour planifié": j
            })

            total_crees += 1

    # === FIN DU TRAITEMENT → API RESPONSE ===
    return jsonify({
        "status": "ok",
        "message_id": "SC_COACH_023" if had_existing else "SC_COACH_024",
        "message": ("🔁 Plan mis à jour" if had_existing else "✅ Séances générées")
                   + f" ({nb_semaines} sem × {jours_final}/sem).",
        "nb_semaines": nb_semaines,
        "jours_par_semaine": jours_final,
        "total": total_crees
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)