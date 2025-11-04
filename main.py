from flask import Flask, request, jsonify
from pyairtable import Api
import os
from datetime import datetime

app = Flask(__name__)

# --- Airtable config ---
AIRTABLE_KEY = os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("BASE_ID")

TABLE_COUR_NAME = os.environ.get("TABLE_COUR")
TABLE_SEANCES_NAME = os.environ.get("TABLE_SEANCES")
TABLE_PLAN_NAME = os.environ.get("TABLE_PLAN")  # 📅 Séances

api = Api(AIRTABLE_KEY)

TABLE_COUR = api.table(BASE_ID, TABLE_COUR_NAME)
TABLE_SEANCES = api.table(BASE_ID, TABLE_SEANCES_NAME)
TABLE_PLAN = api.table(BASE_ID, TABLE_PLAN_NAME)


def weeks_between(d1, d2):
    return max(1, round((d2 - d1).days / 7))


def verifier_jours(fields):
    jours_dispo = fields.get("📅Nb_jours_dispo")
    if not jours_dispo:
        return 1

    try:
        jours_dispo = int(jours_dispo)
    except:
        return 1

    jours_min = fields.get("Jours_min")
    jours_max = fields.get("Jours_max")

    try:
        jours_min = int(jours_min)
        jours_max = int(jours_max)
    except:
        return jours_dispo

    return max(jours_min, min(jours_dispo, jours_max))


@app.post("/generate_by_id")
def generate_by_id():
    data = request.json
    record_id = data.get("id")

    if not record_id:
        return jsonify({
            "status": "error",
            "message_id": "SC_API_001",
            "message": "⚠️ Aucun ID envoyé."
        })

    rec = TABLE_COUR.get(record_id)
    fields = rec["fields"]

    niveau = fields.get("Niveau_normalisé")
    objectif = fields.get("Objectif_normalisé")
    vdot = fields.get("VDOT_utilisé")

    # Durée du plan → basé sur la date objectif
    date_obj = fields.get("Date_objectif")
    nb_semaines = 8
    if date_obj:
        try:
            d_obj = datetime.fromisoformat(date_obj)
            nb_semaines = weeks_between(datetime.today(), d_obj)
        except:
            pass

    jours_final = verifier_jours(fields)

    PHASES_AUTORISEES = ["Prépa générale", "Progression"]

    all_seances = TABLE_SEANCES.all()
    seances_valides = []

    for s in all_seances:
        f = s["fields"]

        if f.get("Mode") != "Running":
            continue
        if f.get("Phase") not in PHASES_AUTORISEES:
            continue

        if niveau not in (f.get("Niveau") or []):
            continue
        if objectif not in (f.get("Objectif") or []):
            continue

        vmin, vmax = f.get("VDOT_min"), f.get("VDOT_max")
        try:
            if vmin and vmax and vdot:
                dv = float(vdot)
                if not (float(vmin) <= dv <= float(vmax)):
                    continue
        except:
            pass

        seances_valides.append(f)

    if not seances_valides:
        return jsonify({
            "status": "error",
            "message_id": "SC_COACH_012",
            "message": "Aucune séance adaptée trouvée.",
            "seances": []
        })

    seances_valides = sorted(seances_valides, key=lambda x: (x.get("Charge", 2), x.get("Durée (min)", 30)))

    # --- CONSTRUCTION DU PLAN ---
    plan = []
    for semaine in range(1, nb_semaines + 1):
        bloc = seances_valides[:jours_final]
        for j, f in enumerate(bloc, start=1):
            record = {
                "NomSéance": f.get("Nom séance"),
                "Type": f.get("Type séance"),
                "Phase": f.get("Phase"),
                "Durée (min)": f.get("Durée (min)"),
                "Charge": f.get("Charge", 2),
                "🧠 Message_coach (modèle)": f.get("🧠 Message_coach (modèle)"),
                "Semaine": semaine,
                "Jour planifié": j,
                "Coureur": [record_id]
            }
            TABLE_PLAN.create(record)
            plan.append(record)

    return jsonify({
        "status": "ok",
        "message": f"✅ {len(plan)} séances générées sur {nb_semaines} semaines.",
        "nb_semaines": nb_semaines,
        "jours_par_semaine": jours_final,
        "total": len(plan)
    })


@app.get("/")
def home():
    return "SmartCoach API active ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))