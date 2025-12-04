# smartcoach_api/scenarios/socle/scn_0a.py
# ====================================================
# SCN_0a : Normalisation et validation du record Airtable

from core.internal_result import InternalResult
from core.utils.logger import get_logger
from services.airtable_tables import ATABLES
from services.airtable_service import AirtableService

log = get_logger("SCN_0a")

def run_scn_0a(context) -> InternalResult:
    """
    SCN_0a : Normalise les données coureur de Airtable
    """

    # --- LECTURE DU RECORD COUREUR ---
    try:
        service = AirtableService()
        service.set_table(ATABLES.COU_TABLE)
        record = service.get_record(context.record_id)

    except Exception as e:
        log.error("[SCN_0a] Impossible de lire le record '%s' (%s)", context.record_id, e)
        return InternalResult(
            status="error",
            message=f"Impossible de lire le record {context.record_id}",
            data={},
            source="SCN_0a"
        )

    # --- LECTURE DU REF NIVEAUX (BEST EFFORT) ---
    try:
        ref_service = AirtableService()
        ref_rows = ref_service.list_all(ATABLES.REF_NIVEAUX)

    except Exception as e:
        log.warning("[SCN_0a] Impossible de lire REF_NIVEAUX (%s)", e)
        ref_rows = []

    # --- PATCH LOCAL SI MATCH REF ---
    if ref_rows:
        ref_match = next(
            (r for r in ref_rows
             if r.get("fields", {}).get("Clé_niveau_reference")
             == record.get("fields", {}).get("Clé_niveau_reference")),
            None
        )

        if ref_match:
            log.info("[SCN_0a] REF_NIVEAUX trouvé pour ce coureur")
            fields = ref_match.get("fields", {})
            for key in ["VDOT_initial", "VDOT_moyen_LK"]:
                if key in fields:
                    record["fields"][key] = fields[key]

    # --- OK ---
    return InternalResult(
        status="ok",
        message="SCN_0a terminé avec succès",
        data={"record_norm": record},
        source="SCN_0a"
    )
