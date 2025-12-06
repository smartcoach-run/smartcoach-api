# ---------------------------------------------------------
# SCN_0a – Normalisation des données coureur (from scratch)
# ---------------------------------------------------------

from core.utils.logger import get_logger
from services.airtable_fields import ATFIELDS

log = get_logger("SCN_0a")


JOURS_ORDONNES = [
    "Lundi", "Mardi", "Mercredi",
    "Jeudi", "Vendredi", "Samedi", "Dimanche"
]


def _normalize_mode(raw: str | None) -> str | None:
    if not isinstance(raw, str):
        return None
    v = raw.strip().lower()
    if v in ("running", "run"):
        return "RUN"
    if v in ("vitalité", "vitalite", "vitalite / bien-être", "vitalite / bien-etre"):
        return "VTL"
    if v in ("kids", "jeunes", "kids & jeunes"):
        return "KIDS"
    if v in ("hyrox", "deka", "hyrox / deka"):
        return "HYROX"
    return None


def _normalize_jours(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(j).strip() for j in raw if isinstance(j, str)]
    return [str(raw).strip()]


def run_scn_0a(context, course_record: dict) -> dict:
    """
    Lit la fiche Coureur Airtable et renvoie un dict normalisé :
    { status, message, data{ objectif, mode, jours_dispos, date_objectif, niveau, objectif_chrono, flags… } }
    """

    fields = course_record.get("fields", {}) or {}

    objectif_norm = fields.get(ATFIELDS.COU_OBJECTIF_NORMALISE)
    mode_raw = fields.get(ATFIELDS.COU_MODE)
    jours_raw = fields.get(ATFIELDS.COU_JOURS_DISPO, []) or []
    niveau_norm = fields.get(ATFIELDS.COU_NIVEAU_NORMALISE)
    date_course = fields.get(ATFIELDS.COU_DATE_COURSE)
    objectif_chrono = fields.get(ATFIELDS.COU_OBJECTIF_CHRONO)

    # 1) Mode
    mode = _normalize_mode(mode_raw)
    if not mode:
        return {
            "status": "error",
            "message": f"Mode invalide ou manquant : {mode_raw!r}",
            "data": {"code": "KO_DATA", "field": "Mode"}
        }

    # 2) Objectif
    if not objectif_norm:
        return {
            "status": "error",
            "message": "Objectif_normalisé manquant",
            "data": {"code": "KO_DATA", "field": "Objectif_normalisé"}
        }
    objectif = str(objectif_norm).strip()

    # 3) Jours disponibles
    jours_dispos = _normalize_jours(jours_raw)
    jours_dispos = [
        j for j in jours_dispos if j in JOURS_ORDONNES
    ]
    if not jours_dispos:
        return {
            "status": "error",
            "message": "Aucun jour disponible valide",
            "data": {"code": "KO_DATA", "field": "Jours disponibles"}
        }

    # 4) Niveau
    niveau = niveau_norm or "Débutant"

    # 5) Date objectif (pour RUN / HYROX = date_course, pour VTL/KIDS on la laissera traiter plus tard)
    date_objectif = date_course

    # 6) Catégorie SmartCoach (pour RUN uniquement)
    cat = None
    obj_up = objectif.upper()
    if mode == "RUN" and obj_up in ("5K", "10K", "HM", "M"):
        cat_map = {"5K": "AS5", "10K": "AS10", "HM": "AS21", "M": "AS42"}
        cat = cat_map.get(obj_up)

    data = {
        "objectif": objectif,
        "mode": mode,
        "jours_dispos": jours_dispos,
        "date_objectif": date_objectif,
        "niveau": niveau,
        "objectif_chrono": objectif_chrono,
        "categorie_smartcoach": cat,
        "is_kids": (mode == "KIDS"),
        "is_vitalite": (mode == "VTL"),
        "is_hyrox": (mode == "HYROX"),
    }

    log.info(f"SCN_0a OK → {data}")

    return {
        "status": "ok",
        "message": "SCN_0a terminé",
        "data": data
    }
