from scenarios.socle.scn_0g import run_scn_0g
from core.internal_result import InternalResult

def run_scn_6(context):
    """
    SCN_6 = Step6 OnDemand
    Génère la séance complète pour un slot donné.
    """
    slot_id = context.payload.get("slot_id")
    record_id = context.record_id

    if not slot_id:
        return InternalResult.error(
            message="slot_id manquant pour SCN_6",
            source="SCN_6"
        )

    if not record_id:
        return InternalResult.error(
            message="record_id manquant pour SCN_6",
            source="SCN_6"
        )

    # ---- PATCH CRUCIAL ----
    # On transmet correctement les inputs attendus par SCN_0g
    inner_context = type("InnerContext", (), {})()
    inner_context.payload = {
        "slot_id": slot_id,
        "record_id": record_id
    }
    inner_context.record_id = record_id

    base = run_scn_0g(inner_context)

    if base.status != "ok":
        return base

    data = base.data

    final = {
        "slot_id": slot_id,
        "categorie": data.get("type"),
        "nom": data.get("modele", "Séance du jour"),
        "details": [
            {"bloc": "WU", "content": "10 min EF"},
            {"bloc": "MAIN", "content": data.get("description")},
            {"bloc": "CD", "content": "10 min EF"},
        ],
        "volume_total": data.get("duree", 25),
        "conseil": data.get("conseils"),
        "ics_block": {
            "title": data.get("mode", "Séance"),
            "duration": data.get("duree", 25),
            "date": data.get("date", None)
        }
    }

    return InternalResult.ok(
        message="SCN_6 généré (Step6 OnDemand)",
        data=final,
        source="SCN_6"
    )
