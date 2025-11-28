from core.internal_result import InternalResult
from scenarios.fonctionnel.scn_1 import run_scn_1
from core.context import SmartCoachContext
from core.utils.logger import get_logger

logger = get_logger("Dispatcher")

SCENARIOS = {
    "SCN_1": run_scn_1,
}


def dispatch_scenario(scn_name: str, record_id: str) -> InternalResult:
    logger.info(f"Dispatcher → Scénario demandé : {scn_name}")

    handler = SCENARIOS.get(scn_name)

    if not handler:
        return InternalResult.make_error(
            message=f"Scénario inconnu : {scn_name}",
            source="Dispatcher"
        )

    context = SmartCoachContext(record_id=record_id)

    try:
        return handler(context)

    except Exception as e:
        logger.exception("Dispatcher → Exception : %s", e)
        return InternalResult.make_error(
            message=f"Erreur interne dans '{scn_name}' : {e}",
            source="Dispatcher"
        )
