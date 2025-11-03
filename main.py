from flask import Flask, request, jsonify
from pyairtable import Api
import os

app = Flask(__name__)

# Chargement des variables Render
AIRTABLE_KEY = os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("BASE_ID")

# Connexion Airtable
api = Api(AIRTABLE_KEY)
print(">>> DEBUG AIRTABLE_KEY =", AIRTABLE_KEY)
print(">>> DEBUG BASE_ID =", BASE_ID)

# Tables (➡️ Utiliser EXACTEMENT les noms affichés dans Airtable)
TABLE_COUR = api.table(BASE_ID, "👤 Coureurs")       # ou "🏃 Coureurs" si c'est le nom affiché
TABLE_SEANCES = api.table(BASE_ID, "🏋️ Séances")     # ou "📘 Séances"

def verifier_jours(fields):
    jours_dispo = fields.get("📅Nb_jours_dispo")
    if jours_dispo is None:
        return "OK", None, 1

    jours_min = fields.get("Jours_min")
    jours_max = fields.get("Jours_max")

    if jours_min is None or jours_max is None:
        return "OK", None, jours_dispo

    try:
        jours_dispo = int(jours_dispo)
        jours_min = int(jours_min)
        jours_max = int(jours_max)
    except:
        return "OK", None, jours_dispo

    if jours_dispo < jours_min:
        return "WARN", "SC_COACH_003", jours_min

    if jours_dispo > jours_max:
        return "WARN", "SC_COACH_004", jours_max

    return "OK", "SC_COACH_002", jours_dispo


@app.post("/generate_by_id")
def generate_by_id():
    data = request.json
    record_id = data.get("id")

    rec = TABLE_COUR.get(record_id)
    fields = rec["fields"]

    niveau = fields.get("Niveau_normalisé")
    objectif = fields.get("Objectif_normalisé")
    vdot = fields.get("VDOT_utilisé")

    _, _, jours_final = verifier_jours(fields)

    PHASES_AUTORISEES = ["Prépa générale", "Progression"]

    all_seances = TABLE_SEANCES.all()
    seances_valides = []

    for s in all_seances:
        f = s.get("fields", {})

        if f.get("Mode") != "Running":
            continue

        if f.get("Phase") not in PHASES_AUTORISEES:
            continue

        niveaux = f.get("Niveau", [])
        if isinstance(niveaux, str):
            niveaux = [niveaux]
        if niveau not in niveaux:
            continue

        objectifs = f.get("Objectif", [])
        if isinstance(objectifs, str):
            objectifs = [objectifs]
        if objectif not in objectifs:
            continue

        vmin = f.get("VDOT_min")
        vmax = f.get("VDOT_max")
        if vmin and vmax and vdot:
            try:
                vdot_f = float(vdot)
                if not (float(vmin) <= vdot_f <= float(vmax)):
                    continue
            except:
                pass

        seances_valides.append({
            "id": s["id"],
            "nom": f.get("NomSéance"),
            "duree_min": f.get("Durée (min)"),
            "type": f.get("Type"),
            "phase": f.get("Phase"),
            "conseil": f.get("🧠 Message_coach (modèle)"),
            "charge": f.get("Charge", 2)
        })

    if len(seances_valides) == 0:
        return jsonify({
            "status": "error",
            "message_id": "SC_COACH_012",
            "message": "Aucune séance adaptée trouvée. Base à compléter.",
            "seances": []
        })

    seances_valides = sorted(seances_valides, key=lambda x: (x["charge"], x["duree_min"]))
    seances_finales = seances_valides[:jours_final]

    return jsonify({
        "status": "ok",
        "message_id": "SC_COACH_021",
        "message": "✅ Sélection optimisée selon ton niveau & ton objectif.",
        "seances": seances_finales,
        "jours_final": jours_final,
        "vdot": vdot
    })


@app.get("/")
def home():
    return "SmartCoach API active ✅"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)