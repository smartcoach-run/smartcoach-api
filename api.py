# api.py

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.config import config               # ← nouvelle config centralisée
from core.context import SmartCoachContext
from core.utils.logger import get_logger
from scenarios.dispatcher import dispatch_scenario
from selftest import router as selftest_router


app = FastAPI()
logger = logging.getLogger("API")
app.include_router(selftest_router)

# =====================================================
#      MODELES DE REQUÊTES
# =====================================================

class GenerateRequest(BaseModel):
    scenario: str
    record_id: str
    payload: dict | None = None


# =====================================================
#      HEALTH CHECK
# =====================================================

@app.get("/health")
def health():
    return {
        "status": "ok" if config.valid else "error",
        "environment": config.env,
        "running_in_fly": config.running_in_fly,
        "airtable_config_ok": config.valid,
    }

# =====================================================
#      ROUTE PRINCIPALE : /generate_by_id
# =====================================================

@app.post("/generate_by_id")
async def generate(body: GenerateRequest):
    logger.info(f"API → /generate_by_id called scenario={body.scenario}")

    scenario = body.scenario
    record_id = body.record_id
    internal_payload = body.payload or {}   # contient mode + run_context

    return dispatch_scenario(scenario, record_id, internal_payload)

# =====================================================
#      ROUTE SPÉCIALE : /generate_sessions
# =====================================================

@app.post("/generate_session")
async def generate_session(body: GenerateRequest):
    """
    Endpoint dédié Step6 OnDemand.
    - scenario doit être "SCN_6" (ou on impose SCN_6 en dur).
    - record_id = coureur Airtable
    - payload.slot_id = identifiant du slot à générer
    """

    logger.info(f"API → generate_session (SCN_6) pour record_id={body.record_id}")

    try:
        # On force le scénario à SCN_6 pour éviter les erreurs de saisie
        result = dispatch_scenario(
            scn_name="SCN_6",
            record_id=body.record_id,
            payload=body.payload or {}
        )

        return {
            "status": "ok",
            "message": "SCN_6 terminé avec succès (Step6 OnDemand)",
            "data": result
        }

    except Exception as e:
        logger.exception(f"Erreur dans generate_session : {e}")
        raise HTTPException(status_code=500, detail=str(e))