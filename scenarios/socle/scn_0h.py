# ⚠️ IMPORTANT
# SCN_0h = persistance STRUCTURE du planning (slots, phases, jours)
# Ne pas utiliser ce module pour persister une exécution de séance.
# Pour cela, utiliser SCN_0h_exec.

# ==========================================================
# SCN_0h — SOCLE — Upsert d’un slot dans Airtable
# ==========================================================

import logging
from core.internal_result import InternalResult
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES
from core.utils.logger import log_info

logger = logging.getLogger("SCN_0h")
ATABLES.SLOTS

def run_scn_0h(context, slot: dict):
    """
    SOCLE : écrit un slot dans la table Slots.
    Aucun métier, aucune orchestration.
    """

    if not slot:
        return InternalResult.error(
            message="SCN_0h : slot manquant",
            source="SCN_0h"
        )

    slot_id = slot.get("slot_id")
    if not slot_id:
        return InternalResult.error(
            message="SCN_0h : slot_id manquant",
            source="SCN_0h"
        )

    # Champs compatibles Airtable
    fields = {
        "Slot_ID": slot_id,
        "Semaine": str(slot.get("semaine") or ""),
        "Jour_nom": slot.get("jour_sem"),
        "Date_slot": slot.get("date_cible"),
        "Phase": slot.get("phase"),
        "Statut": slot.get("status", "planned"),
        "Coureur_ID": context.record_id,
    }

    log_info(f"[SCN_0h] Upsert slot {slot_id} → {fields}")

    try:
        service = AirtableService()     
        record = service.upsert_record(
            ATABLES.SLOTS,      # table_id
            "Slot_ID",          # key_field (champ Airtable)
            slot_id,            # key_value
            fields              # fields
        )

        return InternalResult.ok(
            message=f"SCN_0h : slot {slot_id} enregistré",
            data={"slot_id": slot_id, "fields": fields},
            source="SCN_0h"
        )

    except Exception as e:
        return InternalResult.error(
            message=f"Erreur Airtable SCN_0h : {e}",
            source="SCN_0h"
        )
