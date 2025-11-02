from flask import Flask, request, jsonify
import requests
from qualite.controle_rg import run_all_checks # <- Ton script de vérification RG

app = Flask(__name__)

# Remplace par tes propres identifiants Airtable
AIRTABLE_BASE_ID = "ta_base_id"
AIRTABLE_TABLE_NAME = "🏃 Coureurs"
AIRTABLE_API_KEY = "keyxxxxxxxxxxxx"

@app.route("/")
def index():
    return "API SmartCoach opérationnelle."

@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    data = request.get_json()
    record_id = data.get("id_airtable")

    if not record_id:
        return jsonify({"error": "Missing id_airtable"}), 400

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return jsonify({"error": "Airtable record not found"}), 404

    fields = r.json().get("fields", {})

    return jsonify(fields)

@app.route("/run_all", methods=["POST"])
def run_all():
    data = request.get_json()
    record_id = data.get("id_airtable")

    if not record_id:
        return jsonify({"error": "Missing id_airtable"}), 400

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return jsonify({"error": "Airtable record not found"}), 404

    fields = r.json().get("fields", {})

    try:
        resultats = run_all_checks(fields)
    except Exception as e:
        return jsonify({"error": f"Erreur dans le traitement : {str(e)}"}), 500

    return jsonify(resultats)

if __name__ == "__main__":
    app.run(debug=True)