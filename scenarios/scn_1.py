# scenarios/scn_1.py
# =============================================================
# SCN_1 v1 — Lecture coureur & retour minimal
# Étape 1 : accès Airtable + JSON basique
# =============================================================

from core.internal_result import InternalResult
from core.context import SmartCoachContext
from services.airtable_service import AirtableService
from core.utils.logger import log_info

def run_scn_1(context: SmartCoachContext) -> InternalResult:
    """
    SCN_1 Étape 1 :
    - lire les données du coureur depuis Airtable
    - renvoyer un JSON minimal pour validation
    """

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

    # JSON minimal de vérification
    data = {
        "record_id": context.record_id,
        "prenom": record.get("fields", {}).get("Prénom"),
        "jours_dispo": record.get("fields", {}).get("Jours disponibles"),
        "mode": record.get("fields", {}).get("Mode"),
    }

    log_info(f"SCN_1 → OK (lecture coureur)", module="SCN_1")

    return InternalResult(
        status="ok",
        messages=["SCN_1 étape 1 OK"],
        data=data,
        source="scn_1"
    )
