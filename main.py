from flask import Flask, request, jsonify
import requests
import os
from urllib.parse import quote

from qualite.controle_rg import verifier_vdot, verifier_jours

app = Flask(__name__)

# === Airtable Configuration ===
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
COUREURS_TABLE = os.getenv("AIRTABLE_TABLE_NAME", "🏃 Coureurs")
VDOT_TABLE = os.getenv("AIRTABLE_VDOT_TABLE_NAME", "VDOT_reference")
SEANCES_TABLE = os.getenv("AIRTABLE_SEANCES_TABLE_NAME", "📘 Séances types")


@app.route("/")
def home():
    return "✅ SmartCoach API is running"


@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    """
    API principale :
    - Input : { "id_airtable": "recXXXX" }
    - Output : JSON (status, message_id, vdot, jours_final, séances[])
    """
    data = request.get_json()
    record_id = data.get("id_airtable")

    if not record_id:
        return jsonify({"error": "Missing id_airtable"}), 400

    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}

    # 1) Récupération fiche coureur
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(COUREURS_TABLE)}/{record_id}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return jsonify({"error": "Record not found"}), 404

    record = r.json()
    fields = record.get("fields", {})

    # 2) Vérification / calcul du VDOT
    etat_vdot, message_id, vdot_final = verifier_vdot(fields)
    if etat_vdot == "KO":
        # On ne génère pas de plan → RG bloquante
        return jsonify({"status": "error", "message_id": message_id}), 400

    # 3) Récupération du référentiel Niveaux (min/max jours)
    ref = fields.get("📘 Référentiel Niveaux", [])
    if isinstance(ref, list) and len(ref) > 0:
        # Appel Airtable pour choper les champs Jours_min / Jours_max
        ref_id = ref[0]
        ref_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/📘 Référentiel Niveaux/{ref_id}"
        r_ref = requests.get(ref_url, headers=headers)
        if r_ref.status_code == 200:
            ref_fields = r_ref.json().get("fields", {})
            fields["Jours_min"] = ref_fields.get("Jours_min")
            fields["Jours_max"] = ref_fields.get("Jours_max")

    # 4) Vérification / ajustement des jours (RG B03)
    etat_jours, message_jours, jours_final = verifier_jours(fields)
    fields["📅Nb_jours_final_calcule"] = jours_final

    # 5) Sélection des séances dans 📘 Séances types
    seances_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(SEANCES_TABLE)}"
    r_seances = requests.get(seances_url, headers=headers)
    if r_seances.status_code != 200:
        return jsonify({"status": "error", "message": "Cannot fetch Séances types"}), 500

    data_seances = r_seances.json()
    seances_records = data_seances.get("records", [])

    niveau = fields.get("Niveau_normalisé")
    objectif = fields.get("Objectif_normalisé")
    vdot = float(vdot_final)

    seances_filtrees = []
    for s in seances_records:
        f = s.get("fields", {})

        if f.get("Mode") != "Running":
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

        try:
            vmin = float(f.get("VDOT_min")) if f.get("VDOT_min") is not None else None
            vmax = float(f.get("VDOT_max")) if f.get("VDOT_max") is not None else None
        except:
            continue

        if vmin is not None and vmax is not None:
            if not (vmin <= vdot <= vmax):
                continue

        seances_filtrees.append(s)

    # Tri stable : par durée
    def safe_float(x):
        try:
            return float(x)
        except:
            return 9999

    seances_filtrees = sorted(seances_filtrees, key=lambda s: safe_float(s.get("fields", {}).get("Durée (min)")))

    # Sélection finale : nb = jours_final
    nb = max(1, int(jours_final))
    seances_selection = seances_filtrees[:nb]

    # Formatage sortie
    seances = []
    for s in seances_selection:
        f = s.get("fields", {})
        seances.append({
            "nom": f.get("Nom séance"),
            "duree_min": f.get("Durée (min)"),
            "type": f.get("Type_séance", f.get("Type", None)),
            "phase": f.get("Phase", None),
            "conseil": f.get("🧠 Message_coach (modèle)"),
            "id": s.get("id"),
        })

    # 6) Retour API standardisé
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