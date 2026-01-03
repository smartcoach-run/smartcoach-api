# ⚠️ LEGACY MODULE
# Uses weekday() convention (0–6)
# NOT used by SmartCoach SCN_6
# Kept for backward compatibility (CORE_1 / CORE_3)

from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime, timedelta
from core.utils.logger import get_logger

logger = get_logger("CORE_1")

router = APIRouter(prefix="/core", tags=["CORE_1"])

class Core1Input(BaseModel):
    date_ref: str
    slot_day_index: int

class Core1Output(BaseModel):
    date_slot: str


def compute_first_slot_date(date_ref: str, slot_day_index: int) -> str:
    d = datetime.fromisoformat(date_ref).date()
    while d.weekday() != slot_day_index:
        d += timedelta(days=1)
    return d.isoformat()

def compute_next_slot_date(date_ref: str, day_index: int, days_allowed: list[int]) -> dict:
    """
    date_ref: YYYY-MM-DD
    day_index: int (0=Monday)
    days_allowed: list of int (0–6)
    """

    base_date = datetime.strptime(date_ref, "%Y-%m-%d").date()
    next_date = base_date + timedelta(days=1)

    for _ in range(7):  # sécurité : max 1 semaine
        if next_date.weekday() in days_allowed:
            return {
                "date_slot": next_date.isoformat(),
                "day_index": next_date.weekday()
            }
        next_date += timedelta(days=1)

    raise ValueError("Aucune date valide trouvée pour le prochain slot")

@router.post("/compute_first_slot_date", response_model=Core1Output)

def core_1_compute(input: Core1Input):
    date_slot = compute_first_slot_date(
        date_ref=input.date_ref,
        slot_day_index=input.slot_day_index
    )

    logger.info(
        f"[CORE_1] date_ref={input.date_ref} "
        f"slot_day_index={input.slot_day_index} "
        f"→ date_slot={date_slot}"
    )

    return Core1Output(date_slot=date_slot)

#@router.post("/compute_next_slot_date")
#
# ! Doublon de next_slot.py !
#
#def compute_next_slot(payload: dict):
#    return compute_next_slot_date(
#        payload["date_ref"],
#        payload["day_index"],
#        payload["days_allowed"]
#    )