"""
main.py
Point d’entrée unique du système de génération de plans.

RÔLE :
- Récupérer l’événement Make (payload JSON)
- Charger la configuration (séquence logique Make)
- Dispatcher vers le bon scénario en fonction de Clé_niveau_recherche
- Gérer les exceptions globales pour éviter les crashs Make
"""

import json
from smartcoach_core.config import AIRTABLE_API_KEY, AIRTABLE_BASE_ID
from smartcoach_services.airtable_service import AirtableService
from smartcoach_services.log_service import LogService
from smartcoach_scenarios.dispatcher import dispatch_scenario

airtable = AirtableService(AIRTABLE_API_KEY, AIRTABLE_BASE_ID)
logger = LogService(airtable)


def make_entry(event: dict) -> dict:
    logger.log_event("INFO", "📩 Événement Make reçu", payload=event)

    try:
        if "Clé_niveau_recherche" not in event:
            raise KeyError("Champ manquant : Clé_niveau_recherche")

        response = dispatch_scenario(event)
        logger.log_event("INFO", "✅ Réponse générée", payload=response)
        return response

    except Exception as e:
        logger.log_event("ERREUR", f"❌ Erreur make_entry : {e}", payload=event)
        return {
            "status": "error",
            "message": str(e),
            "input_received": event
        }


if __name__ == "__main__":
    try:
        with open("input.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.log_event("INFO", "MAIN | Input local", payload=data)
        result = dispatch_scenario(data)
        logger.log_event("INFO", "MAIN | Résultat local", payload=result)

        print(result)

    except Exception as e:
        logger.log_event("ERREUR", f"Erreur dans main.py : {e}")
        raise