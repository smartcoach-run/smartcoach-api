# SCN_0g V1 — génération minimale
# Ne pas enrichir sans versionner (V2+)

import logging
from core.internal_result import InternalResult
from core.utils.logger import log_info, log_error

logger = logging.getLogger("SCN_0g")

# ⚠️ SCN_0g V1 — Génération minimale
# Ne pas enrichir sans versionner (V2+)
# Compatible ICS /ics/from-session

def run_scn_0g(context):
    """
    SCN_0g V1 — Génère UNE séance minimale à partir d'UN slot.
    Aucune dépendance externe. Aucune écriture. Aucune orchestration.
    """

    log_info("[SCN_0g] Début génération séance (V1)")

    payload = getattr(context, "payload", None) or {}
    slot = payload.get("slot") or {}

    slot_id = slot.get("slot_id")
    date = slot.get("date")
    slot_type = (slot.get("type") or "EF").upper()

    if not date:
        # Erreur soft : pas de crash, message clair
        log_error("[SCN_0g] Date manquante dans le slot")
        return InternalResult.error(
            message="SCN_0g V1 : date manquante dans le slot",
            source="SCN_0g",
            data={"slot_id": slot_id}
        )

    # Mapping minimal V1
    if slot_type == "EF":
        title = "Séance Endurance fondamentale"
        step_label = "Endurance fondamentale"
        step_type = "E"
        duration_min = 40
        intensity_tags = ["E"]
    else:
        # Fallback V1 volontairement simple
        title = "Séance Endurance fondamentale"
        step_label = "Endurance fondamentale"
        step_type = "E"
        duration_min = 40
        intensity_tags = ["E"]

    session = {
        "title": title,
        "date": date,
        "duration_min": duration_min,
        "steps": [
            {
                "label": step_label,
                "type": step_type,
                "duration_min": duration_min
            }
        ],
        "intensity_tags": intensity_tags
    }

    log_info(f"[SCN_0g] Séance générée (slot_id={slot_id}, type={slot_type})")

    return InternalResult.ok(
        message="SCN_0g V1 : séance générée",
        data={"session": session},
        source="SCN_0g"
    )
