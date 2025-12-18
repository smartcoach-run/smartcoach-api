# scn_slot_resolver.py

from core.internal_result import InternalResult
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES
from core.utils.logger import get_logger

logger = get_logger("SCN_SLOT_RESOLVER")

from datetime import date

def normalize_slot(rec):
    f = rec.get("fields", {}) or {}

    slot_id = (f.get("Slot ID") or "").strip()
    if not slot_id:
        slot_id = rec["id"]

    slot_id = " ".join(slot_id.split())

    status = (f.get("Status") or f.get("Statut") or "").strip().lower()

    return {
        "slot_record_id": rec["id"],
        "slot_id": slot_id,
        "date": f.get("Date"),
        "status": status,
        "type": (f.get("Type") or "").strip(),
    }

def run_scn_slot_resolver(coureur_id: str, mode: str):
    if mode not in ("FIRST", "NEXT", "FEEDBACK"):
        return InternalResult.error(
            message=f"Mode invalide pour SCN_SLOT_RESOLVER: {mode}",
            source="SCN_SLOT_RESOLVER",
        )

    airtable = AirtableService()

    slots = airtable.list_records(
        ATABLES.SLOTS,
        filter_by_formula=f"{{Coureur_ID}} = '{coureur_id}'"
    )

    if not slots:
        return InternalResult.error(
            message="Aucun slot trouvé pour ce coureur",
            source="SCN_SLOT_RESOLVER",
        )

    norm = [normalize_slot(r) for r in slots if r.get("fields")]

    if not norm:
        return InternalResult.error(
            message="Aucun slot normalisable",
            source="SCN_SLOT_RESOLVER",
        )

    eligible = [s for s in norm if s["status"] == "planned"]

    if mode == "FIRST":
        if not eligible:
            return InternalResult.error(
                message="Aucun slot planned trouvé",
                source="SCN_SLOT_RESOLVER",
            )

        eligible.sort(key=lambda s: s["slot_id"])
        selected = eligible[0]

        logger.info(f"SLOTS TOTAL={len(norm)} | ELIGIBLE={len(eligible)}")
        logger.info(
            f"SLOT SELECTED → slot_id={selected['slot_id']} "
            f"status={selected['status']} "
            f"date={selected['date']}"
        )

        return InternalResult.ok(
            data={
                "slot": {
                    "slot_id": selected["slot_id"],
                    "date": selected["date"],
                    "type": selected["type"],
                },
                "reason": "first_planned",
            },
            source="SCN_SLOT_RESOLVER",
        )

    # autres modes volontairement non traités ici
    return InternalResult.error(
        message="Mode non implémenté",
        source="SCN_SLOT_RESOLVER",
    )
