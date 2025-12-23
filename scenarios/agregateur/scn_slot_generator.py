from datetime import datetime, timedelta
from services.airtable_service import AirtableService
from core.internal_result import InternalResult
from core.utils.logger import get_logger
from services.airtable_tables import ATABLES

logger = get_logger("CORE_1")

def run_scn_slot_generator(coureur_id: str):
    airtable = AirtableService()

    records = airtable.list_records(
        ATABLES.SLOTS,
        filter_by_formula=f"{{Coureur}} = '{coureur_id}'",
    )

    if not records:
        return InternalResult.error(
            message="Aucun slot existant pour ce coureur",
            source="SCN_SLOT_GENERATOR",
        )

    slots = []
    for r in records:
        fields = r.get("fields", {})
        date_iso = fields.get("Date_slot")
        if date_iso:
            try:
                slots.append(datetime.fromisoformat(date_iso))
            except Exception:
                pass

    if not slots:
        return InternalResult.error(
            message="Impossible de déterminer une date de référence",
            source="SCN_SLOT_GENERATOR",
        )

    last_date = max(slots)
    next_date = last_date + timedelta(days=2)

    new_record = airtable.create_record(
        ATABLES.SLOTS,
        fields={
            "Coureur": coureur_id,
            "Date_slot": next_date.date().isoformat(),
            "Statut": "planned",
            "Source": "SCN_SLOT_GENERATOR",
        },
    )

    logger.info(
        f"[SCN_SLOT_GENERATOR] Nouveau slot créé "
        f"(slot_id={new_record['id']} date={next_date.date().isoformat()})"
    )

    return InternalResult.ok(
        data={
            "slot": {
                "slot_id": new_record["id"],
                "date": next_date.date().isoformat(),
            }
        },
        source="SCN_SLOT_GENERATOR",
    )