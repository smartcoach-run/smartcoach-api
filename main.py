import os
from dotenv import load_dotenv
from smartcoach_core.dispatcher import run_scenario
from smartcoach_services.log_service import SmartCoachLogger

load_dotenv()
logger = SmartCoachLogger()

if __name__ == "__main__":
    try:
        record_id = os.getenv("RECORD_ID")

        if not record_id:
            raise ValueError("RECORD_ID manquant dans .env")

        logger.log_event("INFO", f"[MAIN] Début génération pour record {record_id}")

        result = run_scenario(record_id)

        logger.log_event("INFO", f"[MAIN] Génération OK pour record {record_id}")

        print("✔ Plan généré avec succès")
        print(result)

    except Exception as e:
        logger.log_event("ERREUR", f"[MAIN] Exception : {e}")
        print("❌ ERREUR :", e)
