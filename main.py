# main.py — SmartCoach Engine API
# Version propre & alignée SCN_1 V1

import os
from flask import Flask, request, jsonify
from smartcoach_services.airtable_service import AirtableService
from smartcoach_scenarios.dispatcher import dispatch_scenario
from smartcoach_services.log_service import log_generation
from smartcoach_core.config import SMARTCOACH_DEBUG
from smartcoach_core.airtable_refs import ATABLES

app = Flask(__name__)

# --------------------------------------------------------------------
# Initialisation Airtable
# --------------------------------------------------------------------
from smartcoach_core.config import get_airtable_credentials
AIRTABLE_API_KEY, AIRTABLE_BASE_ID = get_airtable_credentials()


airtable = AirtableService(api_key=AIRTABLE_API_KEY, base_id=AIRTABLE_BASE_ID)
if SMARTCOACH_DEBUG:
    print("🔗 AirtableService initialisé.")

# --------------------------------------------------------------------
# Endpoint principal : génération par record Airtable
# --------------------------------------------------------------------
@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():

    req = request.json or {}
    record_id = req.get("record_id")
    debug = req.get("debug", False)

    if SMARTCOACH_DEBUG:
        print(f"[API] Reçu → record_id={record_id}, debug={debug}")

    if not record_id:
        return jsonify({"error": "record_id manquant"}), 400

    # --------------------------------------------------
    # 🔍 Charger le coureur depuis Airtable
    # --------------------------------------------------
    try:
        coureur = airtable.get_record(ATABLES.COUREURS, record_id)
    except Exception as e:
        print(f"[CRITICAL] Impossible de charger le coureur : {e}")
        return jsonify({"error": "Record introuvable"}), 404

    # --------------------------------------------------
    # Construire contexte minimal SCN_1
    # --------------------------------------------------
    ctx = {
        "record_id": record_id,
        "coureur": coureur,
        "airtable": airtable,
        "debug": debug,
        "scenario_id": "SCN_1",
    }

    if SMARTCOACH_DEBUG:
        print("🧱 Contexte initial SCN_1 prêt.")
    
    # --------------------------------------------------
    # 🧠 Dispatcher → appel du scénario SCN_1
    # --------------------------------------------------
    try:
        result = dispatch_scenario(ctx)
    except Exception as e:
        print(f"[CRITICAL] Erreur durant l'exécution du scénario : {e}")
        log_generation(
            airtable=airtable,
            record_id=record_id,
            scenario="SCN_1",
            status="START",
            message="Démarrage scénario 1",
        )
        return jsonify({"error": "Erreur interne scénario"}), 500

    # --------------------------------------------------
    # ✏️ Log OK
    # --------------------------------------------------
    try:
        log_generation(
            airtable,
            record_id,
            "SCN_1",
            "OK",
            "Contexte chargé",
        )
    except Exception as e:
        print(f"[WARNING] Impossible d'écrire le log : {e}")

    # --------------------------------------------------
    # Réponse finale API
    # --------------------------------------------------
    return jsonify({
        "status": "OK",
        "record_id": record_id,
        "debug_info": result if debug else None
    })


# --------------------------------------------------------------------
# Lancement API
# --------------------------------------------------------------------
if __name__ == "__main__":
    from datetime import datetime
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("\n" + "="*70)
    print("🚀 SmartCoach Engine prêt à performer !")
    print(f"⏱  Lancement effectué le : {now}")
    print("🔥  Let's build something amazing. Go coach the world.")
    print("🌍  API disponible sur : http://127.0.0.1:8000")
    print("="*70 + "\n")
    
    app.run(host="127.0.0.1", port=8000, debug=True, use_reloader=False)