# scenarios/dispatcher.py

from core.context import SmartCoachContext
from core.internal_result import InternalResult
from core.utils.logger import log_info, log_warning, log_error
from scenarios.scn_0 import run_scn_0
from scenarios.scn_0b import run_scn_0b


def run_scenario(name: str, context: SmartCoachContext) -> InternalResult:
    """Router central du moteur SmartCoach."""

    log_info(f"Scénario demandé : {name}", module="Dispatcher")

    if name == "SCN_0":
        log_info("Exécution SCN_0", module="Dispatcher")
        return run_scn_0(context)

    if name == "SCN_0b":
        log_info("Exécution SCN_0b", module="Dispatcher")
        return run_scn_0b(context)

    log_error(f"Scénario inconnu : {name}", module="Dispatcher")
    raise ValueError(f"Scénario inconnu : {name}")
