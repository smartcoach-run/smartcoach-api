from fastapi import APIRouter
from pydantic import BaseModel
from ics.ics_builder import build_ics

router = APIRouter(prefix="/ics", tags=["ICS"])

class ICSRequest(BaseModel):
    session: dict

@router.post("/from-session")
def generate_ics_from_session(payload: ICSRequest):
    ics_content = build_ics(payload.session)
    return {
        "status": "ok",
        "ics": ics_content
    }
