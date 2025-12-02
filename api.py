import os
import requests
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException   # ← HTTPException OK
from pydantic import BaseModel
from dotenv import load_dotenv               # ← pour charger .env

from core.internal_result import InternalResult
from core.utils.logger import get_logger
from core.context import SmartCoachContext    # ← SmartCoachContext OK

from utils.server_banner import print_startup_banner
from scenarios.dispatcher import dispatch_scenario


# =====================================================
#      CHARGEMENT ENVIRONMENT + BANNER
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")   # Charge ton .env (API KEY, BASE ID, etc.)

HOST = "127.0.0.1"
PORT = 8000
ENV = "dev"

print_startup_banner(HOST, PORT, ENV)

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
#      ROUTE SPÉCIALE : SCN_6 (Génération séances)
# =====================================================

@app.post("/generate_sessions")
def generate_sessions(payload: dict):
    """Exécute SCN_6 directement depuis le payload brut."""
    from scenarios.agregateur.scn_6 import run_scn_6

    # On instancie proprement ton contexte
    context = SmartCoachContext(
        scenario="SCN_6",
        record_id=payload.get("record_id", ""),
        payload=payload
    )

    return run_scn_6(context)
