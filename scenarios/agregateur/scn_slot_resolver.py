from datetime import datetime, timedelta
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES

airtable = AirtableService()

# -------------------------------------------------
# FIRST = création du tout premier slot
# -------------------------------------------------
def run_first(payload: dict):
    coureur_id = payload["coureur_id"]

    records = airtable.list_records(
        ATABLES.SLOTS,
        filter_by_formula=f"AND({{Coureur_ID}} = '{coureur_id}', {{status}} = 'planned')"
    )

    if not records:
        return {
            "success": False,
            "status": "error",
            "message": "Aucun slot FIRST trouvé",
            "source": "SCN_SLOT_RESOLVER"
        }

    # on prend le premier slot planned (pas de tri, pas de magie)
    r = records[0]
    fields = r.get("fields", {})

    slot = {
        "slot_id": r["id"],
        "date": fields.get("Date_slot"),
        "week_index": fields.get("week_index"),
        "day_index": fields.get("day_index"),
    }

    return {
        "success": True,
        "status": "ok",
        "data": {
            "slot": slot,
            "reason": "first_planned"
        },
        "source": "SCN_SLOT_RESOLVER"
    }

# -------------------------------------------------
# NEXT = génération du slot suivant (1 seul)
# -------------------------------------------------
def run_next(payload: dict):
    coureur_id = payload["coureur_id"]
    current_date = payload.get("current_slot_date")

    if not current_date:
        return {
            "success": False,
            "status": "error",
            "message": "current_slot_date manquant",
            "source": "SCN_SLOT_RESOLVER"
        }

    coureur_record = airtable.get_record(ATABLES.COU_TABLE, coureur_id)
    fields = coureur_record.get("fields", {}) if coureur_record else {}
    dispos = fields.get("dispos", [])

    if not dispos:
        return {
            "success": False,
            "status": "error",
            "message": "Aucune disponibilité définie",
            "source": "SCN_SLOT_RESOLVER"
        }

    date = datetime.fromisoformat(current_date)

    for _ in range(14):  # max 2 semaines
        date += timedelta(days=1)
        if date.weekday() in dispos:
            break
    else:
        return {
            "success": False,
            "status": "error",
            "message": "Aucun slot compatible trouvé",
            "source": "SCN_SLOT_RESOLVER"
        }

    slot = {
        "slot_id": f"AUTO_{date.date()}",
        "date": date.date().isoformat(),
        "day_index": date.weekday()
    }

    return {
        "success": True,
        "status": "ok",
        "data": {
            "slot": slot,
            "reason": "next_created"
        },
        "source": "SCN_SLOT_RESOLVER"
    }


# -------------------------------------------------
# POINT D’ENTRÉE UNIQUE APPELÉ PAR L’API
# -------------------------------------------------
def run_scn_slot_resolver(
    coureur_id: str,
    mode: str,
    current_slot_date: str | None = None
):
    mode = mode.upper().strip()

    if mode == "FIRST":
        return run_first({
            "coureur_id": coureur_id
        })

    if mode == "NEXT":
        return run_next({
            "coureur_id": coureur_id,
            "current_slot_date": current_slot_date
        })

    return {
        "success": False,
        "status": "error",
        "message": f"Mode non implémenté : {mode}",
        "source": "SCN_SLOT_RESOLVER"
    }
