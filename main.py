from flask import Flask, request, jsonify
import requests
import os
from urllib.parse import quote
from qualite.controle_rg import verifier_vdot

app = Flask(__name__)

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

# Référentiel VDOT
AIRTABLE_VDOT_TABLE_NAME = os.getenv("AIRTABLE_VDOT_TABLE_NAME", "VDOT_reference")
VDOT_LINK_FIELD_NAME = os.getenv("VDOT_LINK_FIELD_NAME", "📐 VDOT_reference")
VDOT_FIELD_NAME = os.getenv("VDOT_FIELD_NAME", "VDOT")

# Table des séances
AIRTABLE_SEANCES_TABLE_NAME = os.getenv("AIRTABLE_SEANCES_TABLE_NAME", "🏋️ Séances")


def airtable_update(record_id, fields):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    requests.patch(url, headers=headers, json={"fields": fields})


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

    # 2) VDOT fallback via référentiel si besoin
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
        return jsonify({"status": "error", "message_id": message_id}), 400

    # 4) RG Jours (B03-COH)
    nb_jours_dispo = fields.get("📅Nb_jours_dispo")
    ref_ids = fields.get("📘 Référentiel Niveaux", [])
    jours_min = None
    jours_max = None

    if isinstance(ref_ids, list) and len(ref_ids) > 0:
        ref_id = ref_ids[0]
        ref_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/📘 Référentiel Niveaux/{ref_id}"
        r_ref = requests.get(ref_url, headers=headers)
        if r_ref.status_code == 200:
            ref_fields = r_ref.json().get("fields", {})
            jours_min = ref_fields.get("Jours_min")
            jours_max = ref_fields.get("Jours_max")

    if nb_jours_dispo is None or jours_min is None or jours_max is None:
        jours_final = nb_jours_dispo or 1
        message_jours = "SC_COACH_001"
    else:
        if nb_jours_dispo < jours_min:
            jours_final = jours_min
            message_jours = "SC_COACH_002"
        elif nb_jours_dispo > jours_max:
            jours_final = jours_max
            message_jours = "SC_COACH_002"
        else:
            jours_final = nb_jours_dispo
            message_jours = "SC_COACH_001"

    # Écriture du résultat des RG dans Airtable
    airtable_update(record_id, {"📅Nb_jours_final_calcule": jours_final})

    # 5) Sélection des séances
    seances_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(AIRTABLE_SEANCES_TABLE_NAME)}"
    r_seances = requests.get(seances_url, headers=headers)

    if r_seances.status_code != 200:
        return jsonify({"status": "error", "message": "Cannot fetch Séances table"}), 500

    data_seances = r_seances.json().get("records", [])
    seances_filtered = []

    for s in data_seances:
        f = s.get("fields", {})
        vmin = f.get("VDOT_min")
        vmax = f.get("VDOT_max")

        try:
            if vmin is not None: vmin = float(vmin)
            if vmax is not None: vmax = float(vmax)
        except:
            continue

        if vmin <= float(vdot_final) <= vmax:
            seances_filtered.append(s)

    seances_selected = seances_filtered[:max(int(jours_final), 1)]
    seances = [{
        "nom": s["fields"].get("Nom_séance"),
        "structure": s["fields"].get("Structure_séance"),
        "conseil": s["fields"].get("Conseil_coach"),
        "duree": s["fields"].get("Durée_totale_min"),
        "type": s["fields"].get("Type_séance"),
        "id": s.get("id")
    } for s in seances_selected]

    # 6) Retour standardisé
    return jsonify({
        "status": "ok",
        "message_id": message_id,
        "vdot": vdot_final,
        "jours_final": jours_final,
        "seances": seances,
        "fields": fields
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)