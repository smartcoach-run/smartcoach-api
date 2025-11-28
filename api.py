from fastapi import FastAPI
from fastapi.responses import JSONResponse

from utils.server_banner import print_startup_banner
from scenarios.dispatcher import dispatch_scenario
from core.internal_result import InternalResult
from core.utils.logger import get_logger

from dotenv import load_dotenv
load_dotenv()

logger = get_logger("API")

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    print_startup_banner("127.0.0.1", 8000, env="dev")
    logger.info("API → Démarrage terminé")


@app.post("/generate_by_id")
async def generate_by_id(payload: dict):
    logger.info("API → Requête reçue (SCN_1)")

    record_id = payload.get("record_id")
    if not record_id:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "record_id manquant",
                "data": {}
            }
        )

    result = dispatch_scenario("SCN_1", record_id)

    # Sécurisation du type
    if not isinstance(result, InternalResult):
        logger.error("API → Retour inattendu du dispatcher")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Erreur interne"}
        )

    # Construction réponse API
    return JSONResponse(
        status_code=200,
        content={
            "status": result.status,
            "message": result.message,
            "data": result.data
        }
    )
