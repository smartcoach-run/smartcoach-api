# services/extractors.py
# =====================================================
# Fonctions d'extraction génériques depuis Airtable
# =====================================================

from typing import Any, Dict, List

from services.airtable_fields import ATFIELDS


def _normalize_days_list(value: Any) -> List[str]:
    """
    Normalise le champ 'Jours disponibles' ou équivalent en liste de chaînes.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def extract_coureur_step1(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extraction standard des infos coureur pour l'étape 1 de SCN_1
    (et réutilisable pour d'autres scénarios).

    Retourne un dict Make-friendly :
    {
        "prenom": ...,
        "mode": ...,
        "niveau": ...,
        "objectif": ...,
        "jours_dispo": [...],
    }
    """
    fields = record.get("fields", {}) or {}

    jours_dispo_raw = fields.get(ATFIELDS.COU_JOURS_DISPO)
    jours_dispo = _normalize_days_list(jours_dispo_raw)

    return {
        "prenom": fields.get(ATFIELDS.COU_PRENOM),
        "mode": fields.get(ATFIELDS.COU_MODE),
        "niveau": fields.get(ATFIELDS.COU_NIVEAU_NORMALISE),
        "objectif": fields.get(ATFIELDS.COU_OBJECTIF_NORMALISE),
        "jours_dispo": jours_dispo,
    }
