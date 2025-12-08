# api.py

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.config import config               # ← nouvelle config centralisée
from core.context import SmartCoachContext
from core.utils.logger import get_logger
from scenarios.dispatcher import dispatch_scenario

app = FastAPI()
logger = logging.getLogger("API")


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
async def generate_by_id(body: GenerateRequest):
    logger.info(f"API → Requête reçue ({body.scenario})")

    try:
        result = dispatch_scenario(
            scn_name=body.scenario,
            record_id=body.record_id,
            payload=body.payload or {}
        )

        return {
            "status": "ok",
            "message": f"{body.scenario} terminé avec succès (v2025 stable)",
            "data": result
        }

    except Exception as e:
        logger.exception(f"Erreur dans generate_by_id : {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
#      ROUTE SPÉCIALE : /generate_sessions
# =====================================================

@app.post("/generate_sessions")
def generate_sessions(payload: dict):
    from scenarios.agregateur.scn_6 import run_scn_6

    context = SmartCoachContext(
        scenario="SCN_6",
        record_id=payload.get("record_id", "")
    )

    if "week_structure" in payload:
        context.week_structure = payload["week_structure"]
    if "slots" in payload:
        context.slots = payload["slots"]
    if "phases" in payload:
        context.phases = payload["phases"]
    if "objectif_normalise" in payload:
        context.objectif_normalise = payload["objectif_normalise"]

    result = run_scn_6(context)
    return {
        "status": result.status,
        "message": result.message,
        "data": result.data,
        "source": result.source,
    }
