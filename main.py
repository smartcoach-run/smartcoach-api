# main.py
# SmartCoach – Entrée API principale
# Version : v2025-11-18-baseline-SCCTX

from flask import Flask, request, jsonify
from datetime import datetime
import traceback

from smartcoach_core.context import SmartCoachContext
from smartcoach_scenarios.dispatcher import dispatch_scenario

app = Flask(__name__)

# -------------------------------------------------------------------
# 1. Helpers génériques
# -------------------------------------------------------------------

def json_error(message, code="ERROR_TECH", http=200, context=None):
    """Format standard des erreurs SmartCoach."""
    return jsonify({
        "ok": False,
        "status_code": code,
        "record_id": None,
        "scenario_id": None,
        "score_scenario": None,
        "messages": [],
        "errors": [{
            "code": code,
            "message": message,
            "context": context or {}
        }],
        "meta": {
            "duration_ms": 0,
            "version_script": "v2025-11-18",
            "env": "dev",
            "safe_mode": False
        }
    }), http


def validate_request(payload):
    """Validation minimale en attendant le validateur JSON Schema."""
    if not payload:
        return False, "Payload JSON manquant"

    if "record_id" not in payload:
        return False, "record_id manquant"

    return True, None


# -------------------------------------------------------------------
# 2. Endpoint principal Make → SmartCoach
# -------------------------------------------------------------------

@app.route("/generate_by_id", methods=["POST"])
def generate_by_id():
    start = datetime.now()

    try:
        payload = request.get_json(force=True)

        # 2.1 Validation rapide
        ok, err = validate_request(payload)
        if not ok:
            return json_error(err, code="ERROR_PAYLOAD")

        record_id = payload["record_id"]
        debug = payload.get("debug", False)
        source = payload.get("source", "make")
        env = payload.get("env", "dev")

        # 2.2 Construction du contexte minimal
        context = SmartCoachContext(
            record_id=record_id,
            debug=debug,
            source=source,
            env=env
        )

        # 2.3 Appel du moteur SmartCoach
        try:
            result = run_smartcoach_engine(context)

        except Exception as e:
            return json_error(
                "Erreur interne moteur SmartCoach",
                context={"exception": str(e), "type": type(e).__name__}
            )

        # 2.4 Réponse standard
        duration = (datetime.now() - start).total_seconds() * 1000

        # On s'assure que meta existe
        if "meta" not in result:
            result["meta"] = {}

        result["meta"]["duration_ms"] = duration
        return jsonify(result)

    except Exception as e:
        return json_error(
            "Erreur interne API",
            context={"exception": str(e), "trace": traceback.format_exc()}
        )


# -------------------------------------------------------------------
# 3. Moteur SmartCoach (pipeline haut niveau)
# -------------------------------------------------------------------

def run_smartcoach_engine(context: SmartCoachContext):
    """
    Pipeline SmartCoach version baseline.

    Étapes prévues (future) :
      - Fetch Airtable → context.fetch_raw
      - Normalisation → context.normalized
      - Scoring / choix scénario → context.scenario_id / score_scenario
      - Règles RG-xx
      - Génération Plan + Séances + ICS
      - Logs
    """

    # 3.1 Dispatcher → exécute le scénario (SCN-1 pour l'instant)
    context = dispatch_scenario(context)

    # 3.2 Construction de la réponse API standard
    return {
        "ok": len(context.errors) == 0,
        "status_code": "OK" if not context.errors else "ERROR_BUSINESS",
        "record_id": context.record_id,
        "scenario_id": context.scenario_id,
        "score_scenario": context.score_scenario,
        "messages": context.messages,
        "errors": context.errors,
        "meta": {
            "version_script": "v2025-11-18",
            "env": context.env,
            "safe_mode": False,
            "duration_ms": None
        }
    }


# -------------------------------------------------------------------
# 4. Lancement local
# -------------------------------------------------------------------
if __name__ == "__main__":
    import os

    ENV = os.getenv("SMARTCOACH_ENV", "DEV").upper()
    HOT_RELOAD = (ENV == "DEV")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 70)
    print("🚀 SmartCoach Engine – Server starting...")
    print(f"⏱  Start time      : {now}")
    print(f"🌍  Environment    : {ENV}")
    print(f"🔄  Hot Reload     : {'ON' if HOT_RELOAD else 'OFF'}")
    print("📡  API available  : http://127.0.0.1:8000")
    print("=" * 70 + "\n")

    app.run(
        host="127.0.0.1",
        port=8000,
        debug=HOT_RELOAD,
        use_reloader=HOT_RELOAD
    )