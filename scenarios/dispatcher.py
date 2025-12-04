from typing import Dict, Any
from core.internal_result import InternalResult
from core.context import SmartCoachContext
from core.utils.logger import get_logger

# Import des scénarios
from scenarios.agregateur.scn_1 import run_scn_1
from scenarios.agregateur.scn_2 import run_scn_2
from scenarios.agregateur.scn_3 import run_scn_3
from scenarios.agregateur.scn_6 import run_scn_6

logger = get_logger("Dispatcher")


# -------------------------------------------------------------
# Table des scénarios simples (appel direct)
# -------------------------------------------------------------
SCENARIOS = {
    "SCN_1": run_scn_1,
    "SCN_2": run_scn_2,
    "SCN_3": run_scn_3,
    "SCN_6": run_scn_6,
}


# -------------------------------------------------------------
# PIPELINE → SCN_1 → SCN_2 → SCN_3 → SCN_6
# -------------------------------------------------------------
def run_pipeline(context: SmartCoachContext):
    """
    Pipeline complète lorsqu’on appelle SCN_1 :
    SCN_1 → SCN_2 → SCN_3 → SCN_6
    """

    # SCN_1 ----------------------------------------------------
    res1 = run_scn_1(context)
    if res1.status == "error":
        return res1
    context.merge_result(res1)   # <-- important

    # SCN_2 ----------------------------------------------------
    res2 = run_scn_2(context)
    if res2.status == "error":
        return res2
    context.merge_result(res2)

    # SCN_3 ----------------------------------------------------
    res3 = run_scn_3(context)
    if res3.status == "error":
        return res3
    context.merge_result(res3)

    # SCN_6 ----------------------------------------------------
    res6 = run_scn_6(context)
    return res6



# -------------------------------------------------------------
# Dispatcher principal (point d’entrée API)
# -------------------------------------------------------------
def dispatch_scenario(scn_name: str, record_id: str, payload: Dict[str, Any] | None = None):

    logger.info(f"Dispatcher → Scénario demandé : {scn_name}")

    if payload is None:
        payload = {}

    # Contexte SmartCoach
    context = SmartCoachContext(record_id=record_id)

    # Extra-fields (SCN_6)
    extra_fields = ["week_structure", "slots", "phases", "objectif_normalise"]
    for f in extra_fields:
        if f in payload:
            setattr(context, f, payload[f])

    # CAS 1 → Appel pipeline complet
    if scn_name == "SCN_1":
        return run_pipeline(context)

    # CAS 2 → Appel d’un scénario individuel
    handler = SCENARIOS.get(scn_name)
    if not handler:
        return InternalResult.make_error(
            message=f"Scénario inconnu : {scn_name}",
            source="Dispatcher"
        )

    try:
        return handler(context)
    except Exception as e:
        logger.exception("Dispatcher → Exception : %s", e)
        return InternalResult.make_error(
            message=f"Erreur interne dans '{scn_name}' : {e}",
            source="Dispatcher"
        )
