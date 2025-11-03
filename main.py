from flask import Flask, request, jsonify
import requests
import os
from qualite.controle_rg import verifier_vdot
from qualite.controle_rg import verifier_jours

app = Flask(__name__)

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

AIRTABLE_VDOT_TABLE_NAME = os.getenv("AIRTABLE_VDOT_TABLE_NAME", "VDOT_reference")
VDOT_LINK_FIELD_NAME = os.getenv("VDOT_LINK_FIELD_NAME", "📐 VDOT_reference")
VDOT_FIELD_NAME = os.getenv("VDOT_FIELD_NAME", "VDOT")

@app.route("/")
def home():
    return "✅ SmartCoach API is running"

@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    data = request.get_json()
    record_id = data.get("id_airtable")

    if not record_id:
        return jsonify({"error": "Missing id_airtable"}), 400

    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}

    rec_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    r = requests.get(rec_url, headers=headers)

    if r.status_code != 200:
        return jsonify({"error": "Airtable record not found"}), 404

    record = r.json()
    fields = record.get("fields", {})

    # --- VDOT ---
    vdot_utilise = fields.get("VDOT_utilisé") or fields.get("VDOT utilisé")
    if vdot_utilise is None:
        linked_ids = fields.get(VDOT_LINK_FIELD_NAME, [])
        if isinstance(linked_ids, list) and linked_ids:
            ref_id = linked_ids[0]
            ref_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_VDOT_TABLE_NAME}/{ref_id}"
            r_ref = requests.get(ref_url, headers=headers)
            if r_ref.status_code == 200:
                ref_fields = r_ref.json().get("fields", {})
                fields["VDOT_utilisé"] = ref_fields.get(VDOT_FIELD_NAME)

    # --- RG contrôle VDOT ---
    etat_vdot, message_id, vdot_final = verifier_vdot(fields)
    print("VDOT:", etat_vdot, message_id, vdot_final)

    if etat_vdot == "KO":
        return jsonify({"status": "error", "message_id": message_id}), 400

    # --- RG contrôle Jours ---
    etat_jours, message_jours, jours_final = verifier_jours(fields)
    print("JOURS:", etat_jours, message_jours, jours_final)
    fields["📅 Jours_final"] = jours_final

    return jsonify({
        "status": "ok",
        "fields": fields,
        "vdot": vdot_final,
        "message_id": message_id
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)