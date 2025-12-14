import logging
from typing import Any, Dict

from core.internal_result import InternalResult
from core.context import SmartCoachContext
from scenarios.socle.scn_0g import run_scn_0g
from scenarios.run.family_selector import scenario_and_family
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES

logger = logging.getLogger("ROOT")
context = SmartCoachContext()

# ----------------------------------------------------------------------
# Mapping modèle → Type_cible (intensité dominante)
# ----------------------------------------------------------------------
TYPE_CIBLE_BY_FAMILY = {
    "MARA_REPRISE_Q1": "T",
    "GENERIC_EF_Q1": "E",
}

def compute_type_cible(model_family: str) -> str:
    """
    Déduit le Type_cible à partir de la famille de modèle.
    Fallback volontaire sur 'E'.
    """
    return TYPE_CIBLE_BY_FAMILY.get(model_family, "E")

# ======================================================================
#  SCN_6 – Orchestrateur OnDemand (version CLEAN v2026-ready)
# ======================================================================

def run_scn_6(payload, record_id=None):
    logger.info("[SCN_6] Début SCN_6")
    logger.info(f"[SCN_6] PAYLOAD_RECU = {payload}")

    # ✅ CONTEXTE UNIQUE
    context = SmartCoachContext()

    if context.war_room is None:
        context.war_room = {}

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

        # ----------------------------------------------------
        # 2) Extraction du slot
        # ----------------------------------------------------
        slot = run_ctx.get("slot", {}) or {}
        context.slot_id = slot.get("slot_id")
        context.slot_date = slot.get("date")

        # ----------------------------------------------------
        # 3) Extraction du contexte métier NORMALISÉ
        # ----------------------------------------------------
        profile = run_ctx.get("profile", {}) or {}
        objective = run_ctx.get("objective", {}) or {}

        context.mode = profile.get("mode")
        context.submode = profile.get("submode")
        context.age = profile.get("age")

        context.objective_type = objective.get("type")
        context.objective_time = objective.get("time")

        # 🔑 vérité métier normalisée (issue d’Airtable / Make)
        context.objectif_normalisé = run_ctx.get("objectif_normalisé")
        context.war_room["objectif_normalisé"] = context.objectif_normalisé

        # Nettoyage éventuel
        if isinstance(context.objective_time, str):
            context.objective_time = context.objective_time.strip()

        # ----------------------------------------------------
        # 1bis) Validation du run_context
        # ----------------------------------------------------
        if not isinstance(run_ctx, dict) or not run_ctx:
            context.war_room["error"] = "run_context manquant ou vide"
            context.war_room["received_payload"] = payload

            return InternalResult.error(
                message="run_context manquant ou vide",
                source="SCN_6",
                data={"war_room": context.war_room},
            )

        context.war_room["inputs"] = {
            "mode": context.mode,
            "submode": context.submode,
            "objective_type": context.objective_type,
            "objective_time": context.objective_time,
            "objective_time": context.objectif_normalisé,
            "age": context.age,
        }

        # ----------------------------------------------------
        # 4) Sélection scénario + famille via RG-00
        # ----------------------------------------------------
        scenario_id, model_family, scores = scenario_and_family(context)

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
        # 4bis) Calcul du Type_cible (intensité dominante)
        # ----------------------------------------------------
        type_cible = compute_type_cible(model_family)
        context.__dict__["type_cible"] = type_cible
        context.war_room["type_cible"] = type_cible

        # --------------------------------------------------
        # 5) Persistence du Type_cible dans Airtable (Slots)
        # --------------------------------------------------
        try:
            airtable = AirtableService()

            airtable.upsert_record(
                ATABLES.SLOTS,
                key_field="Slot_ID",
                key_value=context.slot_id,
                fields={
                    "Type_cible": context.type_cible
                }
            )
            context.war_room["airtable_update"] = "Type_cible written"

        except Exception as e:
            return InternalResult.error(
                message=f"Erreur Airtable SCN_6 : {str(e)}",
                source="SCN_6",
                data={"war_room": context.war_room},
            )

        # ----------------------------------------------------
        # 5) Exécution SOCLE SCN_0g
        # ----------------------------------------------------
        # ⚠️ Adaptation contrat SCN_0g V1 (payload legacy)
        context.payload = {
            "slot": {
                "slot_id": context.slot_id,
                "date": context.slot_date,
                "type": context.type_cible,  # optionnel mais cohérent
            }
        }
        
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
