# api.py

import os
from fastapi import FastAPI
from pydantic import BaseModel

# Désactiver couleurs lors des appels API (visibilité Postman)
os.environ["SMARTCOACH_NO_COLOR"] = "1"

from core.context import SmartCoachContext
from scenarios.dispatcher import run_scenario
from core.utils.logger import log_info, log_error
from utils.server_banner import print_startup_banner

app = FastAPI(title="SmartCoach Engine")


class GenerateRequest(BaseModel):
    record_id: str
    debug: bool = False
    env: str = "dev"
    source: str = "api"
    scenario: str = "SCN_1"


@app.on_event("startup")
def startup_event():
    host = "127.0.0.1"
    port = 8000

    print_startup_banner(host, port)
    log_info("API → Démarrage terminé", module="API")

@app.post("/generate_by_id")
def generate_by_id(payload: GenerateRequest):

    log_info(f"API → Requête reçue ({payload.scenario})", module="API")

    try:
        context = SmartCoachContext(record_id=payload.record_id)
        result = run_scenario(payload.scenario, context)

        return {
            "status": result.status,
            "messages": result.messages,
            "data": result.data,
            "debug": payload.debug,
            "env": payload.env,
            "source": payload.source,
        }

    except Exception as e:
        log_error(f"Erreur API : {e}", module="API")
        return {
            "status": "error",
            "messages": [str(e)],
            "data": None,
        }