from flask import Flask, request, jsonify
import requests
import os
from urllib.parse import quote
from qualite.controle_rg import verifier_vdot, verifier_jours

app = Flask(__name__)

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

# Référentiel VDOT
AIRTABLE_VDOT_TABLE_NAME = os.getenv("AIRTABLE_VDOT_TABLE_NAME", "VDOT_reference")
VDOT_LINK_FIELD_NAME = os.getenv("VDOT_LINK_FIELD_NAME", "📐 VDOT_reference")
VDOT_FIELD_NAME = os.getenv("VDOT_FIELD_NAME", "VDOT")

# Référentiel niveaux / jours min-max
REF_NIVEAUX_TABLE = os.getenv("AIRTABLE_REF_NIVEAUX_TABLE", "📘 Référentiel Niveaux")
REF_NIVEAUX_LINK = os.getenv("AIRTABLE_REF_NIVEAUX_LINK", "📘 Référentiel Niveaux")

# Table des séances
SEANCES_TABLE_NAME = os.getenv("AIRTABLE_SEANCES_TABLE_NAME", "🏋️ Séances")


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

    # 2) Récupération VDOT depuis lien si besoin
    vdot_utilise = fields.get("VDOT_utilisé")
    if vdot_utilise is None:
        linked_ids = fields.get(VDOT_LINK_FIELD_NAME, [])
        if isinstance(linked_ids, list) and len(linked_ids) > 0:
            linked_id = linked_ids[0]
            ref_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_VDOT_TABLE_NAME}/{linked_id}"
            r_ref = requests.get(ref_url, headers=headers)
            if r_ref.status_code == 200:
                ref_fields = r_ref.json().get("fields", {})
                v = ref_fields.get(VDOT_FIELD_NAME)
                if v is not None:
                    fields["VDOT_utilisé"] = v

    # 3) Vérification RG VDOT
    etat_vdot, message_id, vdot_final = verifier_vdot(fields)
    if etat_vdot == "KO":
        return jsonify({"status": "error", "message_id": message_id}), 400

    # 4) Récupération référentiel jours min/max
    ref_ids = fields.get(REF_NIVEAUX_LINK, [])
    jours_min = None
    jours_max = None

    if isinstance(ref_ids, list) and len(ref_ids) > 0:
        ref_id = ref_ids[0]
        ref_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(REF_NIVEAUX_TABLE)}/{ref_id}"
        r_ref = requests.get(ref_url, headers=headers)
        if r_ref.status_code == 200:
            ref_fields = r_ref.json().get("fields", {})
            jours_min = ref_fields.get("Jours_min")
            jours_max = ref_fields.get("Jours_max")

    # 5) Calcul jours_final via RG
    etat_jours, message_jours, jours_final = verifier_jours(fields)

    try:
        jours_final = int(jours_final)
    except:
        jours_final = 1

    fields["📅Nb_jours_final_calcule"] = jours_final

    # 6) Récupération table Séances (robuste)
    seances_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(SEANCES_TABLE_NAME)}"
    r_seances = requests.get(seances_url, headers=headers)
    if r_seances.status_code != 200:
        return jsonify({"status": "error", "message": "Cannot fetch Séances table"}), 500

    seances_records = r_seances.json().get("records", [])
    seances_filtered = []

    # ✅ Filtrage propre VDOT_min / max
    for s in seances_records:
        f = s.get("fields", {})
        vmin = f.get("VDOT_min")
        vmax = f.get("VDOT_max")

        if vmin is None or vmax is None:
            continue

        try:
            vmin = float(vmin)
            vmax = float(vmax)
        except:
            continue

        if vmin <= float(vdot_final) <= vmax:
            seances_filtered.append(s)

    # 7) Sélection selon jours_final
    seances_selection = seances_filtered[:max(jours_final, 1)]
    seances = [{
        "nom": f.get("Nom_séance"),
        "structure": f.get("Structure_séance"),
        "conseil": f.get("Conseil_coach"),
        "duree": f.get("Durée_totale_min"),
        "type": f.get("Type_séance"),
        "id": s.get("id")
    } for s in seances_selection for f in [s.get("fields", {})]]

    # 8) Retour final standardisé
    return jsonify({
        "status": "ok",
        "message_id": message_id,
        "vdot": vdot_final,
        "jours_final": jours_final,
        "fields": fields,
        "seances": seances
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)