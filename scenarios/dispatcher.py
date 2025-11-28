# scenarios/dispatcher.py

from core.context import SmartCoachContext
from core.utils.logger import log_info, log_error
from services.airtable_service import AirtableService
from scenarios.fonctionnel.scn_1 import run_scn_1

SCENARIOS_MAP = {
    "SCN_1": run_scn_1,
}

def dispatch_scenario(scenario: str, record_id: str):
    log_info(f"Dispatcher → Scénario demandé : {scenario}", module="Dispatcher")

    # Contexte minimal (uniquement scenario + record_id)
    context = SmartCoachContext(
        scenario=scenario,
        record_id=record_id
    )

    # --- CHARGEMENT AIRT ABLE ---
    try:
        airtable = AirtableService()
        record_raw = airtable.get_record(record_id)     # ✅ FIX : record_id, pas context
    except Exception as e:
        log_error(f"Erreur lors de la lecture Airtable : {e}", module="Dispatcher")
        return {
            "status": "error",
            "messages": ["Erreur Airtable → impossible de lire le record"],
            "data": {}
        }

    if not record_raw:
        return {
            "status": "error",
            "messages": ["Record Airtable introuvable ou vide"],
            "data": {}
        }

    # OCR — Enrichir le contexte *après* lecture du record
    context.record_raw = record_raw

    # --- DISPATCH VERS LE BON SCENARIO ---
    handler = SCENARIOS_MAP.get(scenario)
    if not handler:
        log_error(f"Scénario inconnu : {scenario}", module="Dispatcher")
        return {"status": "error", "messages": ["Scénario inconnu"], "data": {}}

    # Exécution
    return handler(context)
