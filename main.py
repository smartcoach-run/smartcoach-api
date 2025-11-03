from flask import Flask, request, jsonify
from pyairtable import Api
import os

app = Flask(__name__)

# --- ENV VARIABLES ---
AIRTABLE_KEY = os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("BASE_ID")
TABLE_COUR_NAME = os.environ.get("TABLE_COUR")             # ex: "🏃 Coureurs"
TABLE_SEANCES_NAME = os.environ.get("TABLE_SEANCES")       # ex: "📘 Séances types"

if not AIRTABLE_KEY or not BASE_ID or not TABLE_COUR_NAME or not TABLE_SEANCES_NAME:
    raise Exception("❌ Variables d'environnement manquantes. Vérifie Render.")

api = Api(AIRTABLE_KEY)
TABLE_COUR = api.table(BASE_ID, TABLE_COUR_NAME)
TABLE_SEANCES = api.table(BASE_ID, TABLE_SEANCES_NAME)


def verifier_jours(fields):
    jours_dispo = fields.get("📅Nb_jours_dispo")
    if jours_dispo is None:
        return "OK", None, 1

    jours_min = fields.get("Jours_min")
    jours_max = fields.get("Jours_max")

    try:
        jours_dispo = int(jours_dispo)
        jours_min = int(jours_min) if jours_min else jours_dispo
        jours_max = int(jours_max) if jours_max else jours_dispo
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

    # --- VALIDATION INPUT ---
    record_id = data.get("id")
    if not record_id:
        return jsonify({
            "status": "error",
            "message": "⚠️ Aucun ID de coureur reçu dans la requête.",
            "message_id": "SC_API_001",
            "expected_format": {"id": "recXXXXXXXXXXXXXX"}
        })

    # --- RÉCUP COUREUR ---
    rec = TABLE_COUR.get(record_id)
    fields = rec.get("fields", {})

    niveau = fields.get("Niveau_normalisé")
    objectif = fields.get("Objectif_normalisé")
    vdot = fields.get("VDOT_utilisé")

    _, _, jours_final = verifier_jours(fields)

    # --- PHASES DÉBUT DE PLAN ---
    PHASES_AUTORISEES = ["Prépa générale", "Progression"]

    # --- FILTRAGE DES SÉANCES ---
    all_seances = TABLE_SEANCES.all()
    seances_valides = []

    for s in all_seances:
        f = s.get("fields", {})

        # Mode Running uniquement
        if f.get("Mode") != "Running":
            continue

        # Phase cohérente
        if f.get("Phase") not in PHASES_AUTORISEES:
            continue

        # Niveau compatible
        niveaux = f.get("Niveau", [])
        if isinstance(niveaux, str):
            niveaux = [niveaux]
        if niveau not in niveaux:
            continue

        # Objectif compatible
        objectifs = f.get("Objectif", [])
        if isinstance(objectifs, str):
            objectifs = [objectifs]
        if objectif not in objectifs:
            continue

        # Filtre VDOT
        vmin = f.get("VDOT_min")
        vmax = f.get("VDOT_max")
        try:
            if vmin is not None and vmax is not None and vdot is not None:
                if not (float(vmin) <= float(vdot) <= float(vmax)):
                    continue
        except:
            pass

        seances_valides.append({
            "id": s["id"],
            "nom": f.get("Nom séance"),
            "duree_min": f.get("Durée (min)"),
            "type": f.get("Type séance"),
            "phase": f.get("Phase"),
            "conseil": f.get("🧠 Message_coach (modèle)"),
            "charge": f.get("Charge", 2)
        })

    # Aucun match trouvé
    if len(seances_valides) == 0:
        return jsonify({
            "status": "error",
            "message_id": "SC_COACH_012",
            "message": "Aucune séance adaptée trouvée. Base à compléter.",
            "seances": []
        })

    # Tri → progressivité
    seances_valides = sorted(seances_valides, key=lambda x: (x["charge"], x["duree_min"]))

    # Sélection finale = nombre de jours validés
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