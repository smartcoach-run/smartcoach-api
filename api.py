# api.py

import os
from pathlib import Path

from dotenv import load_dotenv  # ⬅ import à ajouter

from fastapi import FastAPI
from pydantic import BaseModel

from core.internal_result import InternalResult
from core.utils.logger import get_logger
from utils.server_banner import print_startup_banner
from scenarios.dispatcher import dispatch_scenario

import logging
# Chemin du projet (racine où se trouve ton .env)
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")  # ou simplement load_dotenv() si ton .env est bien à la racine courante

# -----------------------------------------------------
#  App Init + Banner
# -----------------------------------------------------

HOST = "127.0.0.1"
PORT = 8000
ENV = "dev"

print_startup_banner(HOST, PORT, ENV)

app = FastAPI()

logger = logging.getLogger("API")


# -----------------------------------------------------
#  Request Model
# -----------------------------------------------------

class GenerateRequest(BaseModel):
    scenario: str
    record_id: str
    payload: dict | None = None


# -----------------------------------------------------
#  Routes
# -----------------------------------------------------

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
