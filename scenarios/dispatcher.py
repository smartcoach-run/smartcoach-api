from core.internal_result import InternalResult
from core.context import SmartCoachContext
from core.utils.logger import log_info, log_error

from scenarios.scn_1 import run_scn_1


def run_scenario(name: str, context: SmartCoachContext) -> InternalResult:
    """
    Router central du moteur SmartCoach.
    Ajoute ici les futurs scénarios (SCN_2, SCN_ICS, SCN_FEEDBACK…)
    """

    log_info(f"Dispatcher → scénario demandé : {name}")

    # -------------------------------------------
    # SCN_1
    # -------------------------------------------
    if name == "SCN_1":
        log_info("Dispatcher → exécution SCN_1")
        return run_scn_1(context)

    # -------------------------------------------
    # FUTURS SCÉNARIOS (SCN_2, ICS, FEEDBACK…)
    # -------------------------------------------
    # Exemple :
    # if name == "SCN_2":
    #     log_info("Dispatcher → exécution SCN_2")
    #     return run_scn_2(context)

    # -------------------------------------------
    # Erreur si scénario inconnu
    # -------------------------------------------
    log_error(f"Dispatcher → scénario inconnu : {name}")
    raise ValueError(f"Scénario inconnu : {name}")
