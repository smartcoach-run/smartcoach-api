from flask import Flask, request, jsonify
import requests
import os
from qualite.controle_rg import verifier_vdot, verifier_jours

app = Flask(__name__)

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

# Paramètres référentiel VDOT
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

    # 1) Récupération fiche coureur
    rec_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    r = requests.get(rec_url, headers=headers)

    if r.status_code != 200:
        return jsonify({"error": "Airtable record not found"}), 404

    record = r.json()
    fields = record.get("fields", {})

    # 2) Récupération VDOT (fallback via référentiel si besoin)
    vdot_utilise = fields.get("VDOT_utilisé")
    if vdot_utilise is None:
        linked_ids = fields.get(VDOT_LINK_FIELD_NAME, [])
        if isinstance(linked_ids, list) and len(linked_ids) > 0:
            linked_id = linked_ids[0]
            vdot_ref_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_VDOT_TABLE_NAME}/{linked_id}"
            r_ref = requests.get(vdot_ref_url, headers=headers)
            if r_ref.status_code == 200:
                ref_fields = r_ref.json().get("fields", {})
                vdot_from_ref = ref_fields.get(VDOT_FIELD_NAME)
                if vdot_from_ref is not None:
                    fields["VDOT_utilisé"] = vdot_from_ref

    # 3) Vérification RG VDOT
    etat_vdot, message_id, vdot_final = verifier_vdot(fields)
    print("VDOT:", etat_vdot, message_id, vdot_final)

    if etat_vdot == "KO":
        return jsonify({
            "status": "error",
            "message_id": message_id
        }), 400

    # 4) Vérification / ajustement des jours d'entraînement
    etat_jours, message_jours, jours_final = verifier_jours(fields)
    print("JOURS:", etat_jours, message_jours, jours_final)

    # Convertit en entier de manière robuste
    try:
        jours_final = int(jours_final)
    except:
        jours_final = 1  # sécurité minimale (ne bloque jamais)
    fields["📅 Jours_final"] = jours_final


    # 5) Sélection des séances
    seances_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Séances"
    params = {
        "filterByFormula": f"AND({vdot_final} >= {{VDOT_min}}, {vdot_final} <= {{VDOT_max}})"
    }
    r_seances = requests.get(seances_url, headers=headers, params=params)
    seances_records = r_seances.json().get("records", [])

    seances_selection = seances_records[:max(jours_final, 1)]

    seances = []
    for s in seances_selection:
        f = s.get("fields", {})
        seances.append({
            "nom": f.get("Nom_séance"),
            "structure": f.get("Structure_séance"),
            "conseil": f.get("Conseil_coach"),
            "duree": f.get("Durée_totale_min"),
            "type": f.get("Type_séance"),
            "id": s.get("id")
        })

    # 6) Retour API standardisé (pour Make)
    return jsonify({
        "status": "ok",
        "fields": fields,
        "vdot": vdot_final,
        "jours_final": jours_final,
        "seances": seances,
        "message_id": message_id
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)