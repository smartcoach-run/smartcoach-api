from fastapi import APIRouter
from pydantic import BaseModel
import logging

logger = logging.getLogger("SCN_8")

router = APIRouter()

class GenerateSessionInput(BaseModel):
    slot_id: str
    coureur_id: str
    week_index: int
    day_index: int

@router.post("/generate_session")
def generate_session(payload: GenerateSessionInput):

    logger.info(
        f"[SCN_8] generate_session called "
        f"slot_id={payload.slot_id} "
        f"week={payload.week_index} "
        f"day={payload.day_index}"
    )

    # 🔒 TODO étape suivante : vérifier si session existe déjà
    # if session_exists(payload.slot_id):
    #     logger.info("[SCN_8] Session already exists → skip")
    #     return existing_session

    # 🧪 Placeholder volontaire
    session_id = f"sess_{payload.slot_id}"

    logger.info(f"[SCN_8] Session generated → {session_id}")

    return {
        "success": True,
        "session_id": session_id,
        "title": "Séance du jour",
        "summary": "Séance générée (placeholder)",
        "duration_min": 45
    }
