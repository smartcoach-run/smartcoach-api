from fastapi import APIRouter
from pydantic import BaseModel
from scenarios.agregateur.scn_slot_resolver import run_scn_slot_resolver

router = APIRouter()

class ResolveSlotInput(BaseModel):
    coureur_id: str
    mode: str

@router.post("/resolve_slot")
def resolve_slot(payload: ResolveSlotInput):
    result = run_scn_slot_resolver(payload.coureur_id, payload.mode)
    return result.to_api()
