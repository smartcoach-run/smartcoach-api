# smartcoach_services/log_service.py

from smartcoach_core.airtable_refs import ATABLES
from smartcoach_core.airtable_fields import ATFIELDS
from smartcoach_core.config import SMARTCOACH_ENV

def resolve_scenario_record_id(airtable, scenario_code):
    """
    Retourne le record ID Airtable du scénario dans la table liée.
    """
    try:
        # On utilise la formule Airtable sur le champ normalisé du RCTC
        result = airtable.search(
            table_name=ATABLES.SCENARIOS_VALIDATION,
            formula=f"{{ID scénario}} = '{scenario_code}'"
        )

        if result:
            return result[0]["id"]

    except Exception as e:
        print("[LOG][ERROR] Impossible de résoudre le scénario :", e)

    return None

def log_generation(airtable, record_id, scenario, status, message):

    # 🔍 On résout dynamiquement le record ID du scénario
    scenario_record_id = resolve_scenario_record_id(airtable, scenario)

    payload = {
        ATFIELDS.SG_LOG_ID: record_id,
        ATFIELDS.SG_TYPE_SCENARIO: [scenario_record_id] if scenario_record_id else [],
        ATFIELDS.SG_STATUT_EXECUTION: status,
        ATFIELDS.SG_MESSAGE_STATUT: message,
        ATFIELDS.SG_ENVIRONNEMENT: SMARTCOACH_ENV,
    }

    try:
        print("[LOG][DEBUG] Tentative d’écriture :", payload)
        return airtable.create_record(ATABLES.SUIVI_GENERATION, payload)

    except Exception as e:
        print("[LOG ERROR] Impossible d’écrire le log :", e)
        raise  # On remonte pour que le dispatcher puisse afficher l’erreur