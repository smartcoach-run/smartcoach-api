import logging
from typing import Any, Dict

from core.internal_result import InternalResult
from core.context import SmartCoachContext
from engine.bab_engine_mvp import BABEngineMVP
from models.candidates_repo import CandidatesRepository
from scenarios.run.family_selector import select_model_family
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES
from services.airtable_fields import ATFIELDS

logger = logging.getLogger("ROOT")

def _build_phase_rules_from_airtable(records: list[dict]) -> Dict[str, Dict[str, Any]]:
    """
    Construit un dict de règles de phases à partir des enregistrements Airtable.

    Retour attendu par le moteur :
    objectif["phases"] = {
        "Général": {
            "phase": "Général",
            "allure_dominante": ...,
            "duree_min": ...,
            "duree_max": ...,
            "distance_min": ...,
            "distance_max": ...,
            "charge_cible": ...,
            "commentaire": ...
        },
        ...
    }
    """
    phases: Dict[str, Dict[str, Any]] = {}

    for rec in records:
        # Format pyairtable standard : {"id": "...", "fields": {...}}
        fields = rec.get("fields", rec)

        phase_name = fields.get(ATFIELDS.PARAM_PHASE)
        if not phase_name:
            continue

        phases[phase_name] = {
            "phase": phase_name,
            "allure_dominante": fields.get(ATFIELDS.PARAM_PHASE_ALLURE),
            "duree_min": fields.get(ATFIELDS.PARAM_PHASE_DUREE_MIN),
            "duree_max": fields.get(ATFIELDS.PARAM_PHASE_DUREE_MAX),
            "distance_min": fields.get(ATFIELDS.PARAM_PHASE_DISTANCE_MIN),
            "distance_max": fields.get(ATFIELDS.PARAM_PHASE_DISTANCE_MAX),
            "charge_cible": fields.get(ATFIELDS.PARAM_PHASE_CHARGE_CIBLE),
            "commentaire": fields.get(ATFIELDS.PARAM_PHASE_COMMENTAIRE),
        }

    return phases


# ======================================================================
#  SCN_6 – Orchestrateur (Option A : délègue à SCN_0g)
# ======================================================================

from scenarios.socle.scn_0g import run_scn_0g

def run_scn_6(context: SmartCoachContext):

    try:
        # -----------------------------------------------------------------------------------
        # 1) Récupération du payload brut
        # -----------------------------------------------------------------------------------
        payload = getattr(context, "payload", {}) or {}

        # record_id transmis par l’API /generate_by_id
        record_id = getattr(context, "record_id", None)

        run_ctx = payload.get("run_context", {}) or {}

        slot = run_ctx.get("slot", {}) or {}
        context.payload = {
            "slot_id": slot.get("slot_id"),
            "record_id": record_id
        }

        # -----------------------------------------------------------------------------------
        # 2) Préparation du contexte pour SCN_0g
        # -----------------------------------------------------------------------------------
        context.record_id = record_id                 # obligatoire
        context.course_id = record_id                 # facultatif, mais cohérent
        context.slot_id = slot.get("slot_id")         # obligatoire

        logger.info("[SCN_6] Contexte préparé pour SCN_0g : record_id=%s, slot_id=%s",
            context.record_id, context.slot_id)

        # -----------------------------------------------------------------------------------
        # 2.b) Sélection du scénario fonctionnel (v0 : SC-001 seulement)
        # -----------------------------------------------------------------------------------
        try:
            # Extraction des données utiles depuis SmartCoachContext
            user_mode = getattr(context, "mode", None)
            user_submode = getattr(context, "submode", None)
            objective_type = getattr(context, "objective_type", None)
            objective_time = getattr(context, "objective_time", None)
            user_age = getattr(context, "age", None)

            scenario_id = "KO_SCENARIO"

            # --- Conditions exactes du scénario SC-001 ---
            if (
                user_mode == "running"
                and user_submode == "reprise"
                and objective_type == "marathon"
                and objective_time in ("3:45", "3:45:00")
                and (user_age is None or 40 <= user_age <= 55)
            ):
                scenario_id = "SC-001"

            # Initialiser war_room si absent
            war_room = getattr(context, "war_room", {}) or {}
            war_room["scenario_id"] = scenario_id
            context.war_room = war_room

            if scenario_id == "KO_SCENARIO":
                logger.info("[SCN_6] Aucun scénario fonctionnel applicable (v0 : SC-001 uniquement)")
                # Ici on pourrait arrêter, mais pour l’instant on laisse tourner SCN_0g.
                # Pour bloquer la génération : décommenter les 3 lignes suivantes.
                #
                # return InternalResult.error(
                #     message="Aucun scénario fonctionnel applicable (seul SC-001 actif)",
                #     source="SCN_6",
                #     extra={"war_room": war_room}
                # )
            else:
                logger.info(f"[SCN_6] Scénario sélectionné : {scenario_id}")
                # -----------------------------------------------------------------------------------
                # 2.c) Paramétrage SC-001 pour SCN_0g
                # -----------------------------------------------------------------------------------
                if scenario_id == "SC-001":
                    context.target_duration = slot.get("duration") or slot.get("duration_min") or 60
                    context.max_intensity = "T"
                    context.model_family = select_model_family(context)
                    context.session_focus = "ef_plus_tempo_light"
                    context.mode_reprise = True
                    context.phase = "Reprise"

                    # Ajout dans la war_room
                    context.war_room["params"] = {
                        "target_duration": context.target_duration,
                        "max_intensity": context.max_intensity,
                        "model_family": context.model_family,
                        "session_focus": context.session_focus,
                        "mode_reprise": context.mode_reprise,
                        "phase": context.phase,
                    }

                    logger.info("[SCN_6] Paramètres SC-001 appliqués au contexte")


        except Exception as scen_err:
            logger.error("[SCN_6] Erreur sélection scénario : %s", scen_err, exc_info=True)
            # En cas d’erreur, on laisse SCN_0g tourner mais on marque l’erreur dans la war_room
            war_room = getattr(context, "war_room", {}) or {}
            war_room["scenario_id"] = "ERROR_SCENARIO"
            war_room["scenario_error"] = str(scen_err)
            context.war_room["model_family"] = getattr(context, "model_family", None)
            context.war_room = war_room

        # 2) Délégation au moteur SCN_0g

        # -------------------------
        # Injection du slot dans le contexte (obligatoire pour SCN_0g)
        # -------------------------
        context.slot = slot

        logger.info("[SCN_6] Délégation au moteur SCN_0g")
        result_0g = run_scn_0g(context)

        if not result_0g.success:
            raise Exception(f"SCN_0g a échoué : {result_0g.message}")

        data_0g = result_0g.data or {}

        session = data_0g.get("session", {}) or {}
        war_room = result_0g.data.get("war_room", {}) if result_0g.data else {}
        phase_context = result_0g.data.get("phase_context", {}) if result_0g.data else {}

        # 3) Renforcement des champs SCN_6
        session["date"] = slot.get("date")
        session["phase"] = slot.get("phase")
        session["type"] = slot.get("type")
        session["slot_id"] = slot.get("slot_id")

        session.setdefault("metadata", {})
        session["metadata"]["mode"] = payload.get("mode", "ondemand")
        session["metadata"]["socle_version"] = "SCN_6"

        # 4) Structure finale SCN_6
        data_0g = result_0g.data or {}

        session = data_0g.get("session", {}) or {}

        response_payload = {
            "session": session,
            "slot": slot,
            "war_room": data_0g.get("war_room", {}),
            "phase_context": data_0g.get("phase_context", {}),
            "ics_block": None,
            "storage": {}
        }

        logger.info("[SCN_6] Séance générée : OK")

        return InternalResult.ok(
            data=response_payload,
            source="SCN_6",
            message="Séance générée avec SCN_0g via SCN_6"
        )

    except Exception as e:
        logger.error("[SCN_6] Erreur : %s", e, exc_info=True)
        return InternalResult.error(
            message=f"Erreur SCN_6 : {e}",
            source="SCN_6"
        )

def _select_scenario_for_context(ctx) -> str:
    """
    Sélectionne le scénario fonctionnel en fonction du contexte SmartCoach.
    Version v0 : un seul scénario, SC-001 (Marathon 3h45 en mode Reprise).
    Retourne :
      - "SC-001" si le contexte matche
      - "KO_SCENARIO" sinon
    """

    # Les noms d'attributs sont à adapter à ton SmartCoachContext.
    # Hypothèse : ctx.mode, ctx.submode, ctx.objective_type, ctx.objective_time existent.
    try:
        if getattr(ctx, "mode", None) != "running":
            return "KO_SCENARIO"

        if getattr(ctx, "submode", None) != "reprise":
            return "KO_SCENARIO"

        if getattr(ctx, "objective_type", None) != "marathon":
            return "KO_SCENARIO"

        # 3h45 : adapte au format utilisé (string, timedelta, etc.)
        objective_time = getattr(ctx, "objective_time", None)
        if objective_time not in ("3:45", "3:45:00"):
            return "KO_SCENARIO"

        # Optionnel : contrôle de l'âge si tu veux verrouiller davantage
        age = getattr(ctx, "age", None)
        if age is not None and not (40 <= age <= 50):
            return "KO_SCENARIO"

        return "SC-001"

    except Exception:
        # En cas de doute, on ne sélectionne pas SC-001
        return "KO_SCENARIO"
