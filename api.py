import os
from fastapi import FastAPI
from pydantic import BaseModel

from core.context import SmartCoachContext
from scenarios.dispatcher import run_scenario
from utils.server_banner import print_startup_banner
from core.utils.logger import log_info


# -------------------------------------------------------------------
#   Gestion des environnements (DEV / TEST / PROD)
# -------------------------------------------------------------------

ENV  = os.getenv("SMARTCOACH_ENV", "dev")
HOST = os.getenv("SMARTCOACH_HOST", "127.0.0.1")
PORT = os.getenv("SMARTCOACH_PORT", "8000")

# -------------------------------------------------------------------
#   Initialisation FastAPI
# -------------------------------------------------------------------

app = FastAPI(
    title="SmartCoach Engine",
    description="Moteur d'exécution SmartCoach – SOCLE SCN_1",
    version="1.0.0",
)

# -------------------------------------------------------------------
#   Startup event → affiche un banner propre dans VS Code
# -------------------------------------------------------------------

@app.on_event("startup")
def startup_event():
    log_info("API → Démarrage terminé")
    print_startup_banner(HOST, PORT, ENV)

# -------------------------------------------------------------------
#   Modèle d'entrée pour l'API
# -------------------------------------------------------------------

class GenerateRequest(BaseModel):
    record_id: str
    debug: bool = False
    env: str = ENV
    source: str = "api"
    scenario: str = "SCN_1"

# -------------------------------------------------------------------
#   Endpoint principal : exécution d'un scénario SmartCoach
# -------------------------------------------------------------------

@app.post("/generate_by_id")
def generate_by_id(payload: GenerateRequest):
    log_info(f"API → Appel /generate_by_id : SCN={payload.scenario}, record={payload.record_id}")

    context = SmartCoachContext(record_id=payload.record_id)
    result = run_scenario(payload.scenario, context)

    log_info(f"API → SCN terminé : {payload.scenario}")

    return {
        "status": result.status,
        "messages": result.messages,
        "data": result.data,
        "debug": payload.debug,
        "env": payload.env,
        "source": payload.source,
    }

# -------------------------------------------------------------------
#   Endpoint simple de santé / monitoring
# -------------------------------------------------------------------

@app.get("/health")
def health():
    log_info("API → Health-check")
    return {
        "status": "ok",
        "engine": "SmartCoach",
        "env": ENV,
        "version": "1.0.0",
    }
