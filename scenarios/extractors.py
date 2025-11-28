# scenarios/extractors.py
# Extraction des champs Airtable en utilisant ATFIELDS

from core.utils.logger import log_debug
from services.airtable_fields import ATFIELDS


def extract_record_fields(record: dict) -> dict:
    """
    Transforme un record Airtable en un dictionnaire normalisé pour SmartCoach.
    S'appuie UNIQUEMENT sur la classe ATFIELDS.
    """

    log_debug(f"Extractors → Record brut : {record}", module="Extractors")

    fields = record.get("fields", {}) or {}

    return {
        # Champs utilisateur
        "prenom": fields.get(ATFIELDS.COU_PRENOM),
        "email": fields.get(ATFIELDS.COU_EMAIL),
        "genre": fields.get(ATFIELDS.COU_GENRE),
        "age": fields.get(ATFIELDS.COU_AGE),

        # Objectif / Cap
        "cap_choisi": fields.get(ATFIELDS.COU_CAP_CHOISI),
        "objectif_chrono": fields.get(ATFIELDS.COU_OBJECTIF_CHRONO),
        "objectif_normalise": fields.get(ATFIELDS.COU_OBJECTIF_NORMALISE),
        "mode": fields.get(ATFIELDS.COU_MODE),

        # Niveau
        "niveau": fields.get(ATFIELDS.COU_NIVEAU),
        "niveau_normalise": fields.get(ATFIELDS.COU_NIVEAU_NORMALISE),
        "cle_niveau_reference": fields.get(ATFIELDS.COU_CLE_NIVEAU_REF),

        # Course
        "date_course": fields.get(ATFIELDS.COU_DATE_COURSE),
        "date_debut_plan": fields.get(ATFIELDS.COU_DATE_DEBUT_PLAN),

        # Jours disponibles
        "jours_disponibles": fields.get(ATFIELDS.COU_JOURS_DISPO, []),

        # Jours optimisés & final
        "jours_final": fields.get(ATFIELDS.COU_JOURS_FINAL, []),

        # Données diverses du plan
        "duree_plan_calc": fields.get(ATFIELDS.COU_DUREE_PLAN_CALC),
        "test_duree_plan": fields.get(ATFIELDS.COU_TEST_DUREE_PLAN),
    }
