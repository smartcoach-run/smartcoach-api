from fastapi import APIRouter

from pydantic import BaseModel

from ics.ics_builder import build_ics

from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES

router = APIRouter(prefix="/ics", tags=["ICS"])

class ICSRequest(BaseModel):
    session: dict

class ICSFromSCN6Request(BaseModel):
    session: dict
    coureur_id: str | None = None
    start_hour: int = 7

@router.post("/from-session")
def generate_ics_from_session(payload: ICSRequest):
    try:
        ics_content = build_ics(payload.session)
        return {"status": "ok", "ics": ics_content}
    except ValueError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Unexpected ICS error: {e}"}

@router.post("/from-scn6")
def generate_ics_from_scn6(payload: ICSFromSCN6Request):
    session = payload.session
    coureur_id = payload.coureur_id
    start_hour = payload.start_hour

    location = None

    # 🔍 Lookup Airtable du lieu coureur (optionnel)
    if coureur_id:
        airtable = AirtableService()
        record = airtable.get_record(ATABLES.COU_TABLE, coureur_id)
        if record:
            fields = record.get("fields", {})
            location = (
                fields.get("📍 Lieu_final")
                or fields.get("COU_LIEU")
            )

    ics_content = build_ics(
        session=session,
        start_hour=start_hour,
        location=location
    )

    return {
        "status": "ok",
        "ics": ics_content
    }
