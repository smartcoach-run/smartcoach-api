# ==========================================================
# DISPATCHER — Version corrigée (2025-12-08)
# Compatible avec SCN_1 / SCN_2 / SCN_6 dans scenarios/agregateur
# ==========================================================

import logging
from core.utils.logger import log_info
from core.internal_result import InternalResult

# ➜ Tous tes scénarios fonctionnels sont bien dans agregateur
from scenarios.agregateur.scn_1 import run_scn_1
from scenarios.agregateur.scn_2 import run_scn_2
from scenarios.agregateur.scn_6 import run_scn_6

logger = logging.getLogger("Dispatcher")

class SmartCoachContext:
    def __init__(self, scenario, record_id, payload):
        self.scenario = scenario
        self.record_id = record_id
        self.payload = payload or {}


def dispatch_scenario(scn_name: str, record_id: str, payload: dict = None):
    """
    Router principal qui appelle le bon scénario SmartCoach.
    """
    log_info(f"Dispatcher → Scénario demandé : {scn_name}")

    # Construction d’un contexte standard
    context = SmartCoachContext(
        scenario=scn_name,
        record_id=record_id,
        payload=payload or {}
    )

    # ======================================================
    # SCN_1 — Génération du plan (structure)
    # ======================================================
    if scn_name == "SCN_1":
        return run_scn_1(context)

    # ======================================================
    # SCN_2 — Slots + intentions
    # Nécessite data_scn1 (sinon SCN_1 est exécuté automatiquement)
    # ======================================================
    if scn_name == "SCN_2":

        # Make peut envoyer data_scn1
        data_scn1 = context.payload.get("data_scn1")

        # Si absent : exécuter SCN_1 immédiatement
        if not data_scn1:
            norm_res = run_scn_1(context)

            if norm_res.status != "ok":
                return norm_res

            data_scn1 = norm_res.data

        # Appel SCN_2 avec data_scn1 en entrée
        return run_scn_2(context, data_scn1)

    # ======================================================
    # SCN_3 — Non implémenté
    # ======================================================
    if scn_name == "SCN_3":
        return InternalResult.error(
            message="SCN_3 non encore implémenté",
            source="dispatcher"
        )

    logger.info(f"[DISPATCH] Lancement scénario {scn_name}")
    logger.info(f"[DEBUG] DISPATCH INPUT record_id={record_id}")
    logger.info(f"[DEBUG] DISPATCH INPUT payload={payload}")

    # ======================================================
    # SCN_6 — Step6 OnDemand : génération d’une séance
    # ======================================================
    if scn_name == "SCN_6":
        return run_scn_6(context)

    # ======================================================
    # Aucun scénario correspondant → erreur
    # ======================================================
    return InternalResult.error(
        message=f"Scénario inconnu : {scn_name}",
        source="dispatcher"
    )
