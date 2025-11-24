# scenarios/dispatcher.py

from core.context import SmartCoachContext
from core.internal_result import InternalResult
from core.utils.logger import log_info, log_warning, log_error
from scenarios.scn_0 import run_scn_0
from scenarios.scn_0b import run_scn_0b
from scenarios.scn_1 import run_scn_1

def run_scenario(name: str, context: SmartCoachContext) -> InternalResult:
    log_info(f"Scénario demandé : {name}", module="Dispatcher")

    if name == "SCN_0":
        return run_scn_0(context)

    if name == "SCN_0b":
        return run_scn_0b(context)

    if name == "SCN_1":
        return run_scn_1(context)

    raise ValueError(f"Scénario inconnu : {name}")

