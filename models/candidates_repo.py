import logging
from services.airtable_service import AirtableService
import services.airtable_tables as ATABLES
import services.airtable_fields as AFIELDS

logger = logging.getLogger("ROOT")


class CandidatesRepository:
    """
    Charge les séances types depuis Airtable
    et renvoie une liste de candidats utilisables par BAB_ENGINE.
    """

    def __init__(self):
        self.airtable = AirtableService()

    def list_all(self):
        """
        Retourne toutes les séances types avec un mapping propre :
        - code
        - title
        - description
        - intensity_tags
        - duration_min
        - distance_km
        - steps
        """

        logger.info("[CandidatesRepository] Chargement des séances types")

        records = self.airtable.list_all(ATABLES.SEANCES_TYPES_ID)

        candidates = []

        for rec in records:
            f = rec.get("fields", {})

            candidate = {
                "code": f.get("Code"),
                "title": f.get("Nom"),
                "description": f.get("Description"),
                "intensity_tags": f.get("Tags", []),
                "duration_min": f.get("Durée (min)"),
                "distance_km": f.get("Distance (km)"),
                "steps": f.get("Structure_JSON") or [],
            }

            candidates.append(candidate)

        logger.info("[CandidatesRepository] %s séances chargées", len(candidates))
        return candidates
