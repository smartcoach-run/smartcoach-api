from flask import Flask, request, jsonify
import requests
import os
from qualite.controle_rg import verifier_vdot

app = Flask(__name__)

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

@app.route("/")
def home():
    return "✅ SmartCoach API is running"

@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    data = request.get_json()
    record_id = data.get("id_airtable")

    if not record_id:
        return jsonify({"error": "Missing id_airtable"}), 400

    # 1) Récupération du record depuis Airtable
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return jsonify({"error": "Airtable record not found"}), 404

    record = r.json()                  # record complet
    fields = record.get("fields", {})  # juste les champs

    # 2) Vérification VDOT sur les champs
    etat_vdot, message_vdot, vdot_final = verifier_vdot(fields)

    print("VDOT:", etat_vdot, message_vdot, vdot_final)

    if etat_vdot == "KO":
        return jsonify({"erreur": message_vdot}), 400

    # Si tout ok → renvoie les données + VDOT retenu
    return jsonify({
        "fields": fields,
        "vdot": vdot_final,
        "message": message_vdot
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
