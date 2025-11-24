from core.internal_result import InternalResult
from core.context import SmartCoachContext
from core.utils.logger import log_info


def run_scn_1(context: SmartCoachContext) -> InternalResult:
    """
    SCN_1 : Scénario minimal pour valider le pipeline.
    Objectif : prouver que le moteur tourne, du Context → Run → Output.
    """
    log_info("SCN_1 → exécution")

    return InternalResult.ok(
        messages=["SCN_1 exécuté"],
        data={"record_id": context.record_id}
    )

