# scenarios/socle/scn_0a.py

from core.internal_result import InternalResult
from core.utils.logger import log_info, log_error, log_warning
from services.airtable_fields import ATFIELDS


def run_scn_0a(record: dict) -> InternalResult:
    """
    SCN_0a — Validation minimale + normalisation des champs.

    Entrée : record Airtable brut
    Sortie : InternalResult( status="ok", data={...} )
    """

    log_info("SCN_0a → Validation & normalisation", module="APP")

    # ------------------------------------------------------------------
    # 1. Validation du record
    # ------------------------------------------------------------------
    if not record or "id" not in record:
        return InternalResult.error(
            "Record Airtable invalide ou vide",
            source="SCN_0a"
        )

    fields = record.get("fields", {})
    required_fields = [
        ATFIELDS.COU_MODE,
        ATFIELDS.COU_NIVEAU_NORMALISE,
        ATFIELDS.COU_OBJECTIF_NORMALISE,
        ATFIELDS.COU_JOURS_DISPO,
    ]

    # Vérification existence des champs requis
    for key in required_fields:
        if key not in fields:
            return InternalResult.error(
                f"Champ obligatoire manquant : {key}",
                source="SCN_0a"
            )

    # ------------------------------------------------------------------
    # 2. Extraction + normalisation
    # ------------------------------------------------------------------
    try:
        mode = str(fields[ATFIELDS.COU_MODE]).strip()
        niveau = str(fields[ATFIELDS.COU_NIVEAU_NORMALISE]).strip()
        objectif = str(fields[ATFIELDS.COU_OBJECTIF_NORMALISE]).strip()

        jours_raw = fields.get(ATFIELDS.COU_JOURS_DISPO, [])
        if not isinstance(jours_raw, list):
            return InternalResult.error(
                "Le champ Jours_dispo doit être une liste",
                source="SCN_0a"
            )

    except Exception as e:
        log_error(f"SCN_0a → Erreur lors de la normalisation : {e}", module="SCN_0a")
        return InternalResult.error(
            f"Erreur lors de la normalisation : {e}",
            source="SCN_0a"
        )

    # ------------------------------------------------------------------
    # 3. Construction du payload propre
    # ------------------------------------------------------------------
    payload = {
        "mode": mode,
        "niveau": niveau,
        "objectif": objectif,
        "jours_user_raw": jours_raw,
    }

    log_info("SCN_0a → OK", module="APP")
    return InternalResult.ok(
        data=payload,
        source="SCN_0a"
    )