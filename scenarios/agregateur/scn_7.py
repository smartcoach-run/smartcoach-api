# scenarios/agregateur/scn_7.py

import logging
from core.internal_result import InternalResult
from core.utils.logger import log_info, log_error

# from services.airtable_service import AirtableService
# from services.airtable_tables import ATABLES

logger = logging.getLogger("SCN_7")


def run_scn_7(context):
    """
    SCN_7 — Stockage Slot + Session JSON standard.

    context.payload attendu :
    {
        "slot": {...},
        "session": {...},
        "war_room": {...},
        "phase_context": {...},
        "metadata": {
            "mode": "ondemand" | "ics_j-1" | "ics_day" | "regen"
        }
    }
    """

    log_info("[SCN_7] Début scénario 7")

    payload = getattr(context, "payload", None) or {}

    slot = payload.get("slot") or {}
    session = payload.get("session") or {}
    war_room = payload.get("war_room") or {}
    phase_context = payload.get("phase_context") or {}
    metadata = payload.get("metadata") or {}

    slot_id = slot.get("slot_id") or f"slot_{session.get('date', 'unknown')}_{session.get('user_id', 'u')}"

    log_info(f"[SCN_7] slot_id={slot_id}")

    # Construction des champs de stockage
    fields = {
        "Slot ID": slot_id,
        "Date": slot.get("date"),
        "Phase": slot.get("phase"),
        "Type": slot.get("type", "Séance"),
        "Session JSON": session,       # ⚠️ à sérialiser si Airtable attend du texte
        "Phase Context": phase_context,
        "WAR Level": war_room.get("level"),
        "Mode Génération": metadata.get("mode"),
        # TODO: Distance, Durée, Intensités, etc.
    }

    try:
        # TODO : ici, brancher réellement Airtable :
        # at = AirtableService(ATABLES.SLOTS)
        # record = at.upsert_slot(fields)
        record = {"id": "mock_record_id", "fields": fields}
    except Exception as e:
        log_error(f"[SCN_7] Erreur Airtable : {e}")
        return InternalResult.error(
            message=f"Erreur Airtable SCN_7 : {e}",
            source="SCN_7",
            data={"exception": str(e)}
        )

    log_info(f"[SCN_7] ✓ Slot {slot_id} enregistré (mock ou réel).")

    return InternalResult.ok(
        message=f"SCN_7 : slot {slot_id} enregistré",
        data={"slot_id": slot_id, "record": record},
        source="SCN_7"
    )
