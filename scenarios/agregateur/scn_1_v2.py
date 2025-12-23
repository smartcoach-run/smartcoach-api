from datetime import date, timedelta
from typing import List, Dict
from core.internal_result import InternalResult
from core.utils.logger import log_info, log_error
from ics.ics_builder import run_generate_ics

MODULE_NAME = "SCN_1_V2"

# =========================
# Helpers jours / dates
# =========================

DAY_ORDER = {
    "Lundi": 0,
    "Mardi": 1,
    "Mercredi": 2,
    "Jeudi": 3,
    "Vendredi": 4,
    "Samedi": 5,
    "Dimanche": 6,
}

def run_scn_1_v2(context) -> InternalResult:
    """
    Wrapper SOCLE pour SCN_1_V2
    """
    try:
        payload = getattr(context, "payload", {}) or {}

        result = scn_1_v2_init_slots(
            plan_record_id=payload["plan_record_id"],
            user_id=payload["user_id"],
            date_debut=payload["date_debut"],
            nb_semaines=payload["nb_semaines"],
            sessions_per_week=payload["sessions_per_week"],
            dispos=payload["dispos"],
        )

        log_info(
            f"[{MODULE_NAME}] Slots initialisés : {result['slots_created']}",
            module=MODULE_NAME,
        )
        ics_res = run_generate_ics(context)
        
        return InternalResult.ok(
            message="SCN_1_V2 – Slots initialisés",
            source=MODULE_NAME,
            data=result,
        )

    except Exception as e:
        log_error(f"[{MODULE_NAME}] Exception : {e}", module=MODULE_NAME)
        return InternalResult.error(
            message=f"Exception SCN_1_V2 : {e}",
            source=MODULE_NAME,
            data={},
        )

def normalize_and_order_days(dispos: List[str]) -> List[str]:
    """Normalise et ordonne les jours selon l'ordre semaine."""
    return sorted(dispos, key=lambda d: DAY_ORDER[d])


def get_week_dates(week_start: date) -> Dict[str, date]:
    """Retourne un mapping Jour -> Date pour une semaine donnée."""
    return {
        day: week_start + timedelta(days=offset)
        for day, offset in DAY_ORDER.items()
    }


# =========================
# Airtable persistence (stub)
# =========================

def persist_slot(slot_payload: dict):
    """
    Persistance d'un slot dans Airtable.
    À brancher sur airtable_service.create_record("Slots", payload)
    """
    # Exemple :
    # airtable_service.create_record("Slots", slot_payload)
    pass


# =========================
# SCN_1_V2 — Core function
# =========================

def scn_1_v2_init_slots(
    plan_record_id: str,
    user_id: str,
    date_debut: date,
    nb_semaines: int,
    sessions_per_week: int,
    dispos: List[str],
) -> dict:
    """
    Initialise les slots d'un plan (V2 — slot-first).
    """

    # ---------
    # Pré-conditions (fail fast)
    # ---------
    if nb_semaines <= 0:
        raise ValueError("nb_semaines must be > 0")

    if sessions_per_week <= 0:
        raise ValueError("sessions_per_week must be > 0")

    if len(dispos) < sessions_per_week:
        raise ValueError("Not enough available days for sessions_per_week")

    if not date_debut:
        raise ValueError("date_debut is required")

    # ---------
    # Pré-calculs
    # ---------
    total_slots_expected = nb_semaines * sessions_per_week
    ordered_dispos = normalize_and_order_days(dispos)

    slots_created = []
    slot_index = 1
    current_week_start = date_debut

    # ---------
    # Génération des slots
    # ---------
    for week_index in range(1, nb_semaines + 1):

        week_dates = get_week_dates(current_week_start)
        used_days = 0

        for day_index, day_name in enumerate(ordered_dispos, start=1):

            if used_days >= sessions_per_week:
                break

            slot_date = week_dates[day_name]

            slot_payload = {
                "Plan": plan_record_id,
                "User": user_id,
                "Date": slot_date.isoformat(),
                "slot_index": slot_index,
                "week_index": week_index,
                "day_index": day_index,
                "status": "pending",
            }

            persist_slot(slot_payload)
            slots_created.append(slot_payload)

            slot_index += 1
            used_days += 1

        current_week_start = current_week_start + timedelta(days=7)

    # ---------
    # Post-condition
    # ---------
    if len(slots_created) != total_slots_expected:
        raise RuntimeError(
            f"Slot count mismatch: {len(slots_created)} created, "
            f"{total_slots_expected} expected"
        )

    # ---------
    # Retour minimal
    # ---------
    return {
        "plan_record_id": plan_record_id,
        "slots_created": len(slots_created),
        "first_slot": {
            "slot_index": 1,
            "date": slots_created[0]["Date"],
        },
        "cursor": {
            "next_slot_index": 1
        },
    }
