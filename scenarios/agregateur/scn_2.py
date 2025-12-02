import logging
from core.internal_result import InternalResult
from core.context import SmartCoachContext
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES

log = logging.getLogger("SCN_2")

# =====================================================================
# 🇸🇳 SCN_2 — Charger les séances types (version SIMPLE)
# =====================================================================

def run_scn_2(context: SmartCoachContext) -> InternalResult:
    log.info("SCN_2 → Démarrage (mode simple)")

    try:
        # -----------------------------------------------------
        # 1. Charger les séances types via AirtableService
        # -----------------------------------------------------
        airtable = AirtableService()
        ses = airtable.list_all(ATABLES.SEANCES_TYPES)

        log.info(f"SCN_2 → {len(ses)} séances types chargées")

        # -----------------------------------------------------
        # 2. Normaliser la liste
        # -----------------------------------------------------
        cleaned = []
        for rec in ses:
            fields = rec.get("fields", {})
            cleaned.append({
                "id": rec.get("id"),
                "Nom": fields.get("Nom"),
                "Catégorie": fields.get("Catégorie"),
                "Objectif": fields.get("Objectif"),
                "Ordre": fields.get("Ordre"),
                "Description": fields.get("Description"),
            })

        # Pas d’usage de context.fields car SCN_2 est autonome

        return InternalResult.ok(
            message="SCN_2 terminé (simple)",
            data={"seances_types": cleaned},
            source="SCN_2"
        )

    except Exception as e:
        log.error(f"SCN_2 → ERREUR : {e}")

        return InternalResult.make_error(
            message=f"Erreur interne dans SCN_2 : {e}",
            data={},
            source="SCN_2"
        )
