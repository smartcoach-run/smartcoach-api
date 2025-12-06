# ---------------------------------------------------------
# SCN_0c – Calcul du niveau final + VDOT (from scratch)
# ---------------------------------------------------------

from core.utils.logger import get_logger

log = get_logger("SCN_0c")


def run_scn_0c(context, data_0a: dict) -> dict:
    """
    Enrichit les données normalisées avec :
      - niveau_final
      - vdot (None pour l’instant, calcul ajouté plus tard)
    data_0a = data renvoyée par SCN_0a["data"]
    """

    mode = data_0a.get("mode")
    objectif = data_0a.get("objectif")
    niveau = data_0a.get("niveau") or "Débutant"

    # Dans la V1 : on ne calcule PAS le VDOT ici (sera fait via référence VDOT plus tard)
    vdot = None

    out = {
        "niveau_final": niveau,
        "vdot": vdot,
    }

    log.info(f"SCN_0c → {out}")

    return {
        "status": "ok",
        "message": "SCN_0c terminé",
        "data": out
    }
