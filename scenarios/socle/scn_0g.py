# ==========================================================
#  SCN_0g — SOCLE v1.1 (2026-ready)
# ==========================================================

import logging
from typing import Dict, Any

from core.internal_result import InternalResult

logger = logging.getLogger("SCN_0g")


# ----------------------------------------------------------
#  Normalisation steps
# ----------------------------------------------------------

def compute_total_duration(steps):
    total_sec = 0
    for st in steps:
        if st["type"] == "BLOCK":
            repeats = st.get("repeats", 1)
            block_steps = st.get("steps", [])
            for _ in range(repeats):
                total_sec += compute_total_duration(block_steps) * 60
        else:
            if "duration_min" in st:
                total_sec += st["duration_min"] * 60
            elif "duration_sec" in st:
                total_sec += st["duration_sec"]

    return total_sec // 60


def normalize_steps(steps):
    normalized = []

    for st in steps:
        t = st.get("type")
        if not t:
            raise ValueError("Step sans type")

        if t == "BLOCK":
            sub = normalize_steps(st.get("steps", []))
            repeats = st.get("repeats", 1)
            normalized.append({
                "type": "BLOCK",
                "repeats": repeats,
                "steps": sub,
            })
            continue

        # Step simple
        if "duration_min" not in st and "duration_sec" not in st:
            raise ValueError(f"Step {t} sans durée")

        # conversion sec → min
        if "duration_sec" in st and "duration_min" not in st:
            sec = st["duration_sec"]
            st["duration_min"] = max(1, sec // 60)
            del st["duration_sec"]

        normalized.append(st)

    return normalized


# ----------------------------------------------------------
#  Entrée principale SCN_0g
# ----------------------------------------------------------

def run_scn_0g(context):
    logger.info("[SCN_0g] Début SCN_0g")

    model_family = getattr(context, "model_family", None)
    if not model_family:
        return InternalResult.error(
            message="SCN_0g : aucun model_family fourni",
            source="SCN_0g"
        )

    # Dispatcher des modèles SOCLE
    if model_family == "MARA_REPRISE_Q1":
        built = build_mara_reprise_q1(context)
    else:
        return InternalResult.error(
            message=f"SCN_0g : model_family inconnu : {model_family}",
            source="SCN_0g"
        )

    return InternalResult.ok(
        data={
            "session": built["session"],
            "war_room": built["war_room"],
            "phase_context": {},
        },
        source="SCN_0g",
        message=f"Séance générée via modèle {model_family}",
    )


# ----------------------------------------------------------
#  MODELS
# ----------------------------------------------------------

def build_mara_reprise_q1(ctx):
    slot = getattr(ctx, "slot", {}) or {}
    record_id = getattr(ctx, "record_id", None)

    steps = [
        {"type": "EF", "duration_min": 20, "zone": "E"},
        {"type": "BLOCK", "repeats": 3, "steps": [
            {"type": "QUALITY", "duration_min": 5, "zone": "T_LIGHT"},
            {"type": "RECOVER", "duration_min": 3, "zone": "E"},
        ]},
        {"type": "COOLDOWN", "duration_min": 10, "zone": "E"},
    ]

    steps = normalize_steps(steps)
    duration = compute_total_duration(steps)

    session = {
        "session_id": f"sess_{slot.get('slot_id')}",
        "slot_id": slot.get("slot_id"),
        "record_id": record_id,
        "date": slot.get("date"),
        "phase": slot.get("phase"),
        "type": slot.get("type"),
        "steps": steps,
        "duration_total": duration,
        "metadata": {
            "engine_version": "2.0",
            "socle_version": "SCN_0g_v1.1",
            "family": "MARA_REPRISE_Q1",
        },
    }

    war_room = {
        "chosen_model": "MARA_REPRISE_Q1",
        "planned_duration": duration,
    }

    return {
        "session": session,
        "war_room": war_room,
    }
