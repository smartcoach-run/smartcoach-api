# scenarios/scn_1.py
# ============================================================
# SCN_1 – Scénario fonctionnel Running
# Étapes :
#  1) Lecture coureur (Airtable)
#  2) Validations & cohérences (jours min/max)
#  3) Sélection des jours & phases
#  4) Construction du squelette hebdo
# ============================================================

from core.internal_result import InternalResult
from core.context import SmartCoachContext
from core.utils.logger import log_info

from services.airtable_service import AirtableService
from services.airtable_fields import ATFIELDS

from scenarios.validators import validate_running_step2
from scenarios.selectors import build_step3_running
from scenarios.builders import build_step4_running


def run_scn_1(context: SmartCoachContext) -> InternalResult:

    # ---------------------------------------------------------
    # Étape 1 : lecture Airtable
    # ---------------------------------------------------------
    log_info("SCN_1 → lecture coureur depuis Airtable", module="SCN_1")

    airtable = AirtableService()
    record = airtable.get_record(context.record_id)

    if record is None:
        return InternalResult(
            status="ko",
            messages=["Record introuvable"],
            data={"record_id": context.record_id},
            source="scn_1"
        )

    log_info("SCN_1 → Étape 1 OK (lecture coureur)", module="SCN_1")

    # ---------------------------------------------------------
    # Étape 2 : validations & cohérences
    # ---------------------------------------------------------
    step2 = validate_running_step2(record)

    if step2.blocking:
        return InternalResult(
            status="error",
            messages=[err["message"] for err in step2.errors],
            data={"step2": step2.to_dict()},
            source="scn_1"
        )

    step2_data = step2.to_dict().get("data", {})

    # ---------------------------------------------------------
    # Étape 3 : sélection des jours & phases
    # ---------------------------------------------------------
    step3_data = build_step3_running(record, step2_data)

    # ---------------------------------------------------------
    # Étape 4 : squelette hebdomadaire Running
    # ---------------------------------------------------------
    step4_data = build_step4_running(step3_data)

    # ---------------------------------------------------------
    # RÉSULTAT FINAL
    # ---------------------------------------------------------
    return InternalResult(
        status="ok",
        messages=["SCN_1 étape 2 OK"],
        data={
            "record_id": context.record_id,
            "step1": {
                "prenom": record["fields"].get(ATFIELDS.COU_PRENOM),
                "mode": record["fields"].get(ATFIELDS.COU_MODE),
                "niveau": record["fields"].get(ATFIELDS.COU_NIVEAU_NORMALISE),
                "objectif": record["fields"].get(ATFIELDS.COU_OBJECTIF_NORMALISE),
                "jours_dispo": record["fields"].get(ATFIELDS.COU_JOURS_DISPO),
            },
            "step2": step2.to_dict(),
            "step3": step3_data,
            "step4": step4_data
        },
        source="api"
    )
