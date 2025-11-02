from flask import Flask, request, jsonify
import requests
import os

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

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return jsonify({"error": "Airtable record not found"}), 404

    fields = r.json().get("fields", {})
    return jsonify({"fields": fields})

if __name__ == "__main__":
    app.run(debug=True)