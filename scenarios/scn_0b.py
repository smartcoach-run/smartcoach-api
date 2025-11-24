# scenarios/scn_0b.py
# SCN_0b — Diagnostics / API metadata

import platform
import datetime
import os

from services.airtable_service import AirtableService
from core.airtable_refs import ATREFS
from core.context import SmartCoachContext
from core.internal_result import InternalResult
from core.utils.logger import log_info

def run(record_id):
    svc = AirtableService()

    rec = svc.get_record(ATREFS.TBL_COURSEURS, record_id)
    print(rec)
    
def run_scn_0b(context: SmartCoachContext) -> InternalResult:
    """
    SCN_0b : Fournit des informations diagnostics via API :
    - environnement
    - version Python
    - OS
    - timestamp
    """

    log_info("SCN_0b → diagnostic exécuté", module="SCN_0b")

    diagnostics = {
        "timestamp": datetime.datetime.now().isoformat(),
        "env": os.getenv("SMARTCOACH_ENV", "dev"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "record_id": context.record_id,
        "engine": "SmartCoach Engine v1",
    }

    return InternalResult.ok(
        messages=["Diagnostics API OK"],
        data=diagnostics
    )
    # TEST AIRTABLE SI record_id ≠ vide
    airtable_status = "not tested"

    try:
        if context.record_id and context.record_id.upper() != "TEST":
            service = AirtableService()
            rec = service.get_record(context.record_id)

            airtable_status = "ok" if rec else "record_not_found"
    except Exception as e:
        airtable_status = f"error: {str(e)}"

