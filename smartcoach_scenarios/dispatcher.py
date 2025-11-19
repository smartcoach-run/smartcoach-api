# smartcoach_scenarios/dispatcher.py
# ===============================================================
# Dispatcher principal des scénarios SmartCoach.
# V1 : toujours SCN-1 (Running).
#
# FUTUR :
#   - SCN-1 = Running
#   - SCN-2 = Vitalité
#   - SCN-3 = Kids
#   - SCN-4 = Hyrox/DEKA
# ===============================================================

from smartcoach_core.context import SmartCoachContext
from smartcoach_scenarios.scn_1 import run_scn_1


def dispatch_scenario(context: SmartCoachContext) -> SmartCoachContext:
    """
    Choix du scénario SmartCoach.
    V1 : choix forcé de SCN-1.
    """

    scenario_id = "SCN-1"
    context.scenario_id = scenario_id
    context.score_scenario = 1.0  # score maximal pour le scénario unique

    # Appel du scénario réel
    context = run_scn_1(context)

    return context