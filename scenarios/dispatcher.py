from core.context import SmartCoachContext
from core.utils.logger import get_logger

from scenarios.agregateur.scn_1 import run_scn_1
from scenarios.agregateur.scn_3 import run_scn_3
from scenarios.agregateur.scn_6 import run_scn_6

log = get_logger("dispatcher")

# ============================================================
#      ROUTEUR PRINCIPAL
# ============================================================

def dispatch_scenario(scn_name: str, record_id: str, payload: dict):
    """Construit un SmartCoachContext puis route vers le bon scénario."""

    log.info(f"Dispatcher → Scénario demandé : {scn_name}")

    # 1) Construire le contexte complet
    context = SmartCoachContext(
        scenario=scn_name,
        record_id=record_id,
        payload=payload or {}
    )

    # Injecte éventuellement des champs du payload dans le context
    for k, v in payload.items():
        setattr(context, k, v)

    # 2) Router vers le scénario demandé
    if scn_name == "SCN_1":
        return run_scn_1(context)

    if scn_name == "SCN_3":
        return run_scn_3(context)

    if scn_name == "SCN_6":
        return run_scn_6(context)

    raise ValueError(f"Scénario inconnu : {scn_name}")
