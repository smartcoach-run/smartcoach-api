# ---------------------------------------------------------
# SCN_1 – Orchestration du pipeline principal (from scratch)
# ---------------------------------------------------------

from core.utils.logger import get_logger
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES

from scenarios.socle.scn_0a import run_scn_0a
from scenarios.socle.scn_0c import run_scn_0c
from scenarios.socle.scn_0b import run_scn_0b

log = get_logger("SCN_1")


def run_scn_1(context) -> dict:
    # 1) Lecture Airtable
    log.info("SCN_1 → Étape 1 : Lecture Airtable")

    service = AirtableService()
    course_record = service.get_record(
        ATABLES.COU_TABLE,
        context.record_id
    )

    if not course_record:
        return {
            "status": "error",
            "message": f"Record introuvable : {context.record_id}",
            "data": {"code": "KO_TECH"}
        }

    # 2) SCN_0a — normalisation
    log.info("SCN_1 → Étape 2 : Normalisation (SCN_0a)")
    norm = run_scn_0a(context, course_record)

    if norm["status"] != "ok":
        return norm  # on remonte tel quel le KO_DATA

    data = norm["data"]

    # 3) SCN_0c — niveau & VDOT
    log.info("SCN_1 → Étape 3 : Niveau & VDOT (SCN_0c)")
    level = run_scn_0c(context, data)

    if level["status"] != "ok":
        return level

    data.update(level["data"])

    # 4) SCN_0b — optimisation jours
    log.info("SCN_1 → Étape 4 : Optimisation jours (SCN_0b)")
    days = run_scn_0b(context, data)

    if days["status"] != "ok":
        return days

    data.update(days["data"])

    # 5) Sortie finale SCN_1
    return {
        "status": "ok",
        "message": "SCN_1 terminé (socle 0a/0c/0b exécuté)",
        "data": data
    }
