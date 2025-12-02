from typing import Dict, Any
from core.internal_result import InternalResult
from core.context import SmartCoachContext
from core.utils.logger import get_logger

# Import des scénarios
from scenarios.agregateur.scn_1 import run_scn_1
from scenarios.agregateur.scn_2 import run_scn_2
from scenarios.agregateur.scn_6 import run_scn_6


logger = get_logger("Dispatcher")


# ----------------------------------------------------------------------
#  TABLE DES SCENARIOS DISPONIBLES
# ----------------------------------------------------------------------
SCENARIOS = {
    "SCN_1": run_scn_1,
    "SCN_2": run_scn_2,
    "SCN_6": run_scn_6,
}


# ----------------------------------------------------------------------
#  DISPATCHER PRINCIPAL
# ----------------------------------------------------------------------
def dispatch_scenario(scn_name: str, record_id: str, payload: Dict[str, Any] | None = None):
    """
    Route vers le bon scénario en fonction du nom.
    Fournit automatiquement un SmartCoachContext.
    """
    logger.info(f"Dispatcher → Scénario demandé : {scn_name}")

    if payload is None:
        payload = {}

    # Vérification scénario
    handler = SCENARIOS.get(scn_name)
    if not handler:
        return InternalResult.make_error(
            message=f"Scénario inconnu : {scn_name}",
            source="Dispatcher"
        )

    # Création du contexte minimal (conforme à core/context.py)
    context = SmartCoachContext(record_id=record_id)

    # ------------------------------------------------------------------
    #  PATCH SCN_6 : transmission manuelle de données (step3 → step4 → step5)
    # ------------------------------------------------------------------
    # Le contexte n'a pas de .payload → injection via setattr()
    extra_fields = ["week_structure", "slots", "phases"]

    for field in extra_fields:
        if field in payload:
            setattr(context, field, payload[field])

    # ------------------------------------------------------------------
    #  EXECUTION DU SCENARIO
    # ------------------------------------------------------------------
    try:
        return handler(context)

    except Exception as e:
        logger.exception("Dispatcher → Exception : %s", e)
        return InternalResult.make_error(
            message=f"Erreur interne dans '{scn_name}' : {e}",
            source="Dispatcher"
        )
