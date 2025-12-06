# ---------------------------------------------------------
# SCN_0b – Optimisation simple des jours (from scratch)
# ---------------------------------------------------------

from core.utils.logger import get_logger

log = get_logger("SCN_0b")

JOURS_ORDONNES = [
    "Lundi", "Mardi", "Mercredi",
    "Jeudi", "Vendredi", "Samedi", "Dimanche"
]


def run_scn_0b(context, data_0x: dict) -> dict:
    """
    Reçoit data_0x (data après SCN_0a/0c) et renvoie :
      - jours_optimises : liste triée selon l’ordre standard
    V1 : pas encore de Safe Mode / espacement avancé.
    """

    jours = data_0x.get("jours_dispos") or []
    if not isinstance(jours, list):
        jours = [jours]

    jours_valides = [j for j in jours if j in JOURS_ORDONNES]

    if not jours_valides:
        return {
            "status": "error",
            "message": "Aucun jour valide pour SCN_0b",
            "data": {"code": "KO_DATA", "field": "jours_dispos"}
        }

    jours_sorted = sorted(jours_valides, key=lambda j: JOURS_ORDONNES.index(j))

    out = {
        "jours_optimises": jours_sorted
    }

    log.info(f"SCN_0b → {out}")

    return {
        "status": "ok",
        "message": "SCN_0b terminé",
        "data": out
    }
