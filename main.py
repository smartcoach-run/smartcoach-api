from flask import Flask, request, jsonify
from pyairtable import Table
from datetime import datetime
import os

app = Flask(__name__)

import os
from pyairtable import Table

API_KEY = os.environ.get("AIRTABLE_KEY")
BASE_ID = os.environ.get("BASE_ID")

TABLE_COUR_NAME = os.environ.get("TABLE_COUR")
TABLE_SEANCES_NAME = os.environ.get("TABLE_SEANCES")
TABLE_ARCHIVES_NAME = os.environ.get("TABLE_ARCHIVES")
TABLE_MODELES_NAME = os.environ.get("TABLE_MODELES")
TABLE_SEANCES_TYPES_NAME = os.environ.get("TABLE_SEANCES_TYPES")

TABLE_COUR = Table(API_KEY, BASE_ID, TABLE_COUR_NAME)
TABLE_SEANCES = Table(API_KEY, BASE_ID, TABLE_SEANCES_NAME)
TABLE_ARCHIVES = Table(API_KEY, BASE_ID, TABLE_ARCHIVES_NAME)
TABLE_MODELES = Table(API_KEY, BASE_ID, TABLE_MODELES_NAME)
TABLE_SEANCES_TYPES = Table(API_KEY, BASE_ID, TABLE_SEANCES_TYPES_NAME)

@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    data = request.get_json()
    record_id = data.get("record_id")

    # --- Récup coureur ---
    coureur = TABLE_COUR.get(record_id)["fields"]

    jours_dispo = coureur.get("📅 Jours disponibles", [])
    jours_final = len(jours_dispo)
    nb_semaines = int(coureur.get("⏱️ Nb semaines", 8))

    # --- Récup version plan et incrément ---
    version_actuelle = coureur.get("Version plan", 0)
    nouvelle_version = version_actuelle + 1

    # --- Récup séances existantes pour archivage ---
    existing = TABLE_SEANCES.all(
        formula=f"{{Coureur}} = '{record_id}'"
    )

    if existing:
        for s in existing:
            fields = s["fields"]

            TABLE_ARCHIVES.create({
                "Coureur": fields.get("Coureur"),
                "Nom séance": fields.get("Nom séance"),
                "Type séance": fields.get("Type séance"),
                "Durée (min)": fields.get("Durée (min)"),
                "Charge": fields.get("Charge"),
                "Semaine": fields.get("Semaine"),
                "Jour planifié": fields.get("Jour planifié"),
                "Phase": fields.get("Phase"),
                "Clé séance": fields.get("Clé séance"),
                "🧠 Message coach": fields.get("🧠 Message coach"),
                "Version plan": version_actuelle,
                "Date archivage": datetime.utcnow().isoformat()
            })

        # Suppression des séances actives
        for s in existing:
            TABLE_SEANCES.delete(s["id"])

    # --- Mise à jour Version plan coureur ---
    TABLE_COUR.update(record_id, {"Version plan": nouvelle_version})

    # --- Récup modèles de séances valides ---
    seances_configs = TABLE_MODELES.all()
    seances_valides = [m["fields"] for m in seances_configs]

    total_crees = 0

    for semaine in range(1, nb_semaines + 1):
        bloc = seances_valides[:jours_final]

        for j, f in enumerate(bloc, start=1):

            type_brut = f.get("Type séance") or f.get("Type")
            type_final = type_brut[0] if isinstance(type_brut, list) else type_brut

            TABLE_SEANCES.create({
                "Coureur": [record_id],
                "Nom séance": f.get("Nom séance"),
                "Type séance": type_final,
                "Durée (min)": f.get("Durée (min)"),
                "Charge": f.get("Charge", 2),
                "Semaine": semaine,
                "Jour planifié": j,
                "Version plan": nouvelle_version
            })

            total_crees += 1

    return jsonify({
        "status": "ok",
        "message_id": "SC_COACH_024",
        "message": f"✅ Nouveau plan généré — **Version {nouvelle_version}**\n{total_crees} séances créées ({nb_semaines} sem × {jours_final}/sem).",
        "nb_semaines": nb_semaines,
        "jours_par_semaine": jours_final,
        "total": total_crees,
        "version_plan": nouvelle_version
    })


@app.route("/", methods=["GET"])
def home():
    return "SmartCoach API active ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
