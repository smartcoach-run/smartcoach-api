# scenarios/scn_0.py
# SCN_0 — Test moteur minimal

from core.context import SmartCoachContext
from core.internal_result import InternalResult
from core.utils.logger import log_info


def run_scn_0(context: SmartCoachContext) -> InternalResult:
    """
    SCN_0 : Vérification du moteur SmartCoach.
    Retourne un OK simple avec record_id.
    """

    log_info("SCN_0 → test moteur OK", module="SCN_0")

    return InternalResult.ok(
        messages=["SCN_0 exécuté"],
        data={
            "record_id": context.record_id,
            "engine_status": "healthy"
        }
    )
