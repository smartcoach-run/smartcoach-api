# api.py

import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from ics.ics_builder import build_ics
from pydantic import BaseModel

from core.config import config               # ← nouvelle config centralisée
from core.context import SmartCoachContext
from core.utils.logger import get_logger
from scenarios.dispatcher import dispatch_scenario
from ics import router as ics_router
from selftest import router as selftest_router

app = FastAPI()

app.include_router(ics_router)
app.include_router(selftest_router)

logger = logging.getLogger("API")

# =====================================================
#      MODELES DE REQUÊTES
# =====================================================

class GenerateRequest(BaseModel):
    scenario: str
    record_id: str
    payload: dict | None = None

class GenerateSessionRequest(BaseModel):
    """
    Requête minimale pour SCN_0g (Step6 OnDemand).
    Alignée avec SCN_0g V1.
    """
    slot: Dict[str, Any]

    # Champs optionnels pour compatibilité future
    scenario: Optional[str] = None
    record_id: Optional[str] = None

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

from scenarios.socle.scn_0g import run_scn_0g

@app.post("/generate_session")
async def generate_session(body: GenerateSessionRequest):
    """
    Endpoint technique Step6-OnDemand.
    Appelle directement le SOCLE SCN_0g.
    """
    logger.info("API → generate_session (SOCLE SCN_0g)")

    try:
        context = SmartCoachContext(
            scenario="SCN_0g",
            record_id=body.record_id,
            payload={
                "slot": body.slot
            }
        )

        result = run_scn_0g(context)

        return {
            "status": "ok",
            "message": "SCN_0g exécuté avec succès",
            "data": result
        }

    except Exception as e:
        logger.exception(f"Erreur dans generate_session : {e}")
        return {
            "success": False,
            "status": "error",
            "message": f"Erreur API : {e}",
            "source": "API",
            "data": None,
            "context": None
        }
# =====================================================
#      ROUTE DEBUG SOCLE : /socle/scn_0h_exec
# =====================================================

from scenarios.socle.scn_0h import run_scn_0h

class PersistSlotRequest(BaseModel):
    slot: Dict[str, Any]
    record_id: str

@app.post("/socle/scn_0h_exec")
async def socle_scn_0h_exec(body: PersistSlotRequest):
    """
    Route TECHNIQUE de debug local pour SCN_0h.
    ❌ Jamais appelée par Make
    """
    logger.info("API → socle/scn_0h_exec (DEBUG SOCLE)")

    try:
        context = SmartCoachContext(
            scenario="SCN_0h",
            record_id=body.record_id,
            payload={}
        )

        result = run_scn_0h(
            context=context,
            slot=body.slot
        )

        return {
            "status": "ok",
            "message": "SCN_0h exécuté avec succès",
            "data": result
        }

    except Exception as e:
        logger.exception(f"Erreur SCN_0h : {e}")
        raise HTTPException(status_code=500, detail=str(e))
