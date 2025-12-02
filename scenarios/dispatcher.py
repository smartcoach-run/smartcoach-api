from core.internal_result import InternalResult
from scenarios.agregateur.scn_1 import run_scn_1
from scenarios.agregateur.scn_6 import run_scn_6
from core.context import SmartCoachContext
from core.utils.logger import get_logger
from typing import Any, Optional, Dict

logger = get_logger("Dispatcher")


SCENARIOS = {
    "SCN_1": run_scn_1,
    "SCN_6": run_scn_6,
}


def dispatch_scenario(scn_name: str, record_id: str, payload: Dict = None):
    if payload is None:
        payload = {}
    logger.info(f"Dispatcher → Scénario demandé : {scn_name}")

    handler = SCENARIOS.get(scn_name)

    if not handler:
        return InternalResult.make_error(
            message=f"Scénario inconnu : {scn_name}",
            source="Dispatcher"
        )

    context = SmartCoachContext(record_id=record_id)

    # Patch SCN_6 : si des données SCN_1 sont transmises dans la requête API,
    # on les injecte dans le contexte
    extra_fields = ["week_structure", "slots", "phases"]
    for field in extra_fields:
        if field in payload:   # payload = request body JSON
            setattr(context, field, payload[field])

    try:
        return handler(context)

    except Exception as e:
        logger.exception("Dispatcher → Exception : %s", e)
        return InternalResult.make_error(
            message=f"Erreur interne dans '{scn_name}' : {e}",
            source="Dispatcher"
        )
