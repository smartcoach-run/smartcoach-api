import logging
from typing import Any, Dict

from core.internal_result import InternalResult
from core.context import SmartCoachContext
from scenarios.socle.scn_0g import run_scn_0g
from scenarios.run.family_selector import select_scenario_and_family

logger = logging.getLogger("ROOT")


# ======================================================================
#  SCN_6 – Orchestrateur OnDemand (version CLEAN v2026-ready)
# ======================================================================

def run_scn_6(payload, record_id=None):
    logger.info("[SCN_6] Début SCN_6")
    logger.info(f"[SCN_6] PAYLOAD_RECU = {payload}")

    try:
        # ----------------------------------------------------
        # 1) Extraction universelle du run_context
        # ----------------------------------------------------
        if isinstance(payload, dict):
            run_ctx = payload.get("run_context", {}) or {}

        elif hasattr(payload, "payload") and isinstance(payload.payload, dict):
            run_ctx = payload.payload.get("run_context", {}) or {}

        else:
            run_ctx = getattr(payload, "run_context", {}) or {}

        slot = run_ctx.get("slot", {}) or {}

        # ----------------------------------------------------
        # 2) Construction du SmartCoachContext interne
        # ----------------------------------------------------
        context = SmartCoachContext()
        context.record_id = record_id
        context.slot_id = slot.get("slot_id")
        context.payload = payload   # brut
        context.__dict__["slot"] = slot
        context.__dict__["war_room"] = {}

        # ----------------------------------------------------
        # 3) Extraction profil / objectif → hydratation dynamique
        # ----------------------------------------------------
        profile = run_ctx.get("profile", {}) or {}
        objectif = run_ctx.get("objectif", {}) or {}

        context.__dict__["mode"] = objectif.get("discipline", "").lower()
        context.__dict__["submode"] = objectif.get("experience", "").lower()
        context.__dict__["objective_type"] = objectif.get("type", "").lower()
        context.__dict__["objective_time"] = objectif.get("chrono_cible")
        context.__dict__["age"] = profile.get("age")

        context.war_room["inputs"] = {
            "mode": context.mode,
            "submode": context.submode,
            "objective_type": context.objective_type,
            "objective_time": context.objective_time,
            "age": context.age,
        }

        # ----------------------------------------------------
        # 4) Sélection scénario + famille via RG-00
        # ----------------------------------------------------
        scenario_id, model_family, scores = select_scenario_and_family(context)

        context.war_room["scenario_id"] = scenario_id
        context.war_room["model_family"] = model_family
        context.war_room["scores"] = scores

        if scenario_id == "KO_SCENARIO":
            return InternalResult.error(
                message="Aucun scénario fonctionnel applicable",
                source="SCN_6",
                data={"war_room": context.war_room},
            )

        # Injection du modèle dans le contexte pour SCN_0g
        context.__dict__["model_family"] = model_family

        # ----------------------------------------------------
        # 5) Exécution SOCLE SCN_0g
        # ----------------------------------------------------
        result = run_scn_0g(context)

        if not result.success:
            raise RuntimeError(f"SCN_0g a échoué : {result.message}")

        final_data = result.data or {}
        final_data["war_room"] = context.war_room

        # ----------------------------------------------------
        # 6) Réponse finale
        # ----------------------------------------------------
        return InternalResult.ok(
            data=final_data,
            source="SCN_6",
            message="Séance générée avec SCN_0g via SCN_6",
        )

    except Exception as e:
        logger.exception("[SCN_6] Exception")
        return InternalResult.error(
            message=f"Erreur SCN_6 : {e}",
            source="SCN_6",
        )
