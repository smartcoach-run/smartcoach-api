import logging
from core.utils.logger import log_info, log_error
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

# ----------------------------------------------------------------------
# P3-E – Mémoire courte feedback J-1 / J-2
# ----------------------------------------------------------------------

def compute_adaptive_context(feedback_slots):
    """
    Calcule le contexte adaptatif à partir des slots feedback (J-1 / J-2).
    feedback_slots : liste de records Airtable (dict)
    """
    states = []

    for slot in feedback_slots or []:
        fields = slot.get("fields", {}) or {}
        etat = fields.get("feedback_etat")
        if etat:
            states.append(etat)

    count_fatigued = states.count("fatigued")
    has_good = "good" in states

    if count_fatigued >= 2:
        return {
            "perceived_state": "fatigued",
            "fatigue_streak": 2,
            "memory_window": "J-1/J-2",
            "rule": "RG_MEM_001_PERSISTENT_FATIGUE",
        }

    if count_fatigued == 1 and not has_good:
        return {
            "perceived_state": "fatigued",
            "fatigue_streak": 1,
            "memory_window": "J-1/J-2",
            "rule": "RG_MEM_001_SINGLE_FATIGUE",
        }

    if has_good:
        return {
            "perceived_state": "good",
            "fatigue_streak": 0,
            "memory_window": "J-1/J-2",
            "rule": "RG_MEM_001_GOOD_STATE",
        }

    return {
        "perceived_state": "neutral",
        "fatigue_streak": 0,
        "memory_window": "J-1/J-2",
        "rule": "RG_MEM_001_NEUTRAL",
    }

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

    # ✅ GARDE-FOU GLOBAL SCN_2
    if context.adaptation is None:
        context.adaptation = {
            "perceived_state": "neutral",
            "fatigue_streak": 0
        }
        context.war_room["adaptation_initialized_default"] = True

    try:
        # ----------------------------------------------------
        # 1) Extraction universelle du run_context
        # ----------------------------------------------------
        if isinstance(payload, dict):
            run_ctx = payload.get("run_context", {}) or {}

            # ----------------------------------------------------
            # GARDE-FOU SCN_2 : adaptation TOUJOURS présente
            # (même sans feedback utilisateur)
            # ----------------------------------------------------
            if "adaptation" not in run_ctx:
                run_ctx["adaptation"] = {
                    "perceived_state": "neutral",
                    "fatigue_streak": 0
                }
        elif hasattr(payload, "payload") and isinstance(payload.payload, dict):
            run_ctx = payload.payload.get("run_context", {}) or {}
        else:
            run_ctx = getattr(payload, "run_context", {}) or {}
        # ----------------------------------------------------
        # 1ter) Extraction des feedbacks slots (P3-E)
        # ----------------------------------------------------
        if isinstance(payload, dict):
            feedback_slots = payload.get("feedback_slots", [])
        elif hasattr(payload, "payload") and isinstance(payload.payload, dict):
            feedback_slots = payload.payload.get("feedback_slots", [])
        else:
            feedback_slots = []

        context.war_room["feedback_slots_count"] = len(feedback_slots)

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
        context.level = profile.get("level")

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

        # ----------------------------------------------------
        # 4ter) Calcul du contexte adaptatif (P3-E)
        # ----------------------------------------------------
        adaptive_context = compute_adaptive_context(feedback_slots)
        context.__dict__["adaptive_context"] = adaptive_context
        context.war_room["adaptive_context"] = adaptive_context

        # ----------------------------------------------------
        # 4quater) Initialisation adaptation (contrat SCN_2)
        # ----------------------------------------------------
        adaptation = {
            "perceived_state": adaptive_context.get("perceived_state"),
            "fatigue_streak": adaptive_context.get("fatigue_streak", 0),
        }

        # ✅ écrasement contrôlé
        context.adaptation = adaptation
        context.war_room["adaptation_overridden_by_P3E"] = True
        
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
        # 5) Exécution SOCLE SCN_0g / SCN_2
        # ----------------------------------------------------
        # ⚠️ Adaptation contrat SCN_0g V1 (payload legacy)

        incoming_run_context = run_ctx

        engine_version = incoming_run_context.get("engine_version")
        mode = (incoming_run_context.get("profile", {}).get("mode") or "").lower()
        if "adaptation" not in incoming_run_context:
            incoming_run_context["adaptation"] = {
                "perceived_state": "neutral",
                "fatigue_streak": 0
            }

        # ----------------------------------------------------
        # 5bis-ter) Injection adaptation dans run_context (contrat SCN_2 réel)
        # ----------------------------------------------------
        incoming_run_context["adaptation"] = {
            "perceived_state": adaptive_context.get("perceived_state"),
            "fatigue_streak": adaptive_context.get("fatigue_streak", 0),
        }

        context.war_room["adaptation_injected_in_run_context"] = True

        # ----------------------------------------------------
        # Initialisation du phase_context (contrat SCN_2)
        # ----------------------------------------------------
        phase_context = {}
        context.war_room["phase_context_initialized"] = True

        # ----------------------------------------------------
        # 5bis-final) Payload conforme au contrat SCN_2
        # ----------------------------------------------------
        context.payload = {
            "run_context": incoming_run_context,   # ✅ clé attendue par SCN_2
            "phase_context": phase_context,        # ✅ clé attendue par SCN_2

            # (optionnel) on garde aussi le legacy si SCN_0g en a besoin
            "slot": {
                "slot_id": context.slot_id,
                "date": context.slot_date,
                "type": getattr(context, "type_cible", None),
            },
            "profile": {
                "level": context.level
            }
        }

        context.war_room["payload_contract"] = "SCN_2_run_context"

        if engine_version == "C" and mode == "running":
            log_info("[SCN_6] engine_version=C → utilisation SCN_2")
            from scenarios.agregateur.scn_2 import run_scn_2
            result = run_scn_2(context)
        else:
            log_info("[SCN_6] fallback SCN_0g (V1)")
            from scenarios.socle.scn_0g import run_scn_0g
            result = run_scn_0g(context)


        if not result.success:
            raise RuntimeError(f"SCN_0g a échoué : {result.message}")

        final_data = result.data or {}
        final_data["war_room"] = context.war_room
        # ----------------------------------------------------
        # 6) Réponse finale
        # ----------------------------------------------------
        engine_label = "SCN_2" if engine_version == "C" else "SCN_0g"

        return InternalResult.ok(
            message=f"Séance générée avec {engine_label} via SCN_6",
            source="SCN_6",
            data=final_data,
        )

    except Exception as e:
        logger.exception("[SCN_6] Exception")
        return InternalResult.error(
            message=f"Erreur SCN_6 : {e}",
            source="SCN_6",
        )

