import logging
from typing import Any, Dict

from core.internal_result import InternalResult
from core.context import SmartCoachContext
from engine.bab_engine_mvp import BABEngineMVP
from models.candidates_repo import CandidatesRepository
from scenarios.run.family_selector import select_scenario_and_family
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

#A SUPPRIMER
def detect_scenario(context):
    """
    Analyse le contexte utilisateur et renvoie l’ID du scénario fonctionnel.
    """
    mode = context.mode
    submode = context.submode
    obj_type = context.objective_type
    obj_time = context.objective_time
    age = context.age

    # SC-001 — Marathon 3h45 Reprise 40-55 ans
    if (
        mode == "running"
        and submode == "reprise"
        and obj_type == "marathon"
        and obj_time in ("3:45", "3:45:00")
        and (age is None or 40 <= age <= 55)
    ):
        return "SC-001"

    return "KO_SCENARIO"
#A SUPPRIMER
def dispatch_model(context, scenario_id):
    """
    Retourne le model_family à utiliser selon le scénario identifié.
    """
    if scenario_id == "SC-001":
        return "MARA_REPRISE_Q1"

    return "GENERIC_EF_Q1"

def run_scn_6(payload, record_id=None):
    logger.info("[SCN_6] Début SCN_6")
    logger.info(f"[SCN_6] PAYLOAD_RECU = {payload}")
    try:
        # ----------------------------------------------------
        # Lecture universelle du payload racine
        # payload peut être :
        #  - un dict (appel direct API)
        #  - un SmartCoachContext (appel depuis dispatcher SCN)
        # ----------------------------------------------------

        if isinstance(payload, dict):
            # Appel direct depuis API → JSON brut
            run_ctx = payload.get("run_context", {}) or {}

        elif hasattr(payload, "payload") and isinstance(payload.payload, dict):
            # Appel depuis dispatcher → JSON stocké dans context.payload
            run_ctx = payload.payload.get("run_context", {}) or {}

        else:
            # Dernier fallback : tenter d'accéder directement
            run_ctx = getattr(payload, "run_context", {}) or {}

        slot = run_ctx.get("slot", {}) or {}

        # ----------------------------------------------------
        # Construction du contexte interne
        # ----------------------------------------------------
        context = SmartCoachContext()

        # Identifiants
        context.record_id = record_id
        context.slot_id = slot.get("slot_id")

        # On stocke le payload brut si besoin
        context.payload = payload

        # Slot complet pour SCN_0g (variable interne, pas champ pydantic)
        context.__dict__["slot"] = slot

        # War room
        context.__dict__["war_room"] = {}

        # ----------------------------------------------------
        # Extraction du profil / objectif → injection dans le contexte
        # ----------------------------------------------------
        profile = run_ctx.get("profile", {}) or {}
        objectif = run_ctx.get("objectif", {}) or {}

        context.__dict__["mode"] = objectif.get("discipline", "").lower()
        context.__dict__["submode"] = objectif.get("experience", "").lower()
        context.__dict__["objective_type"] = objectif.get("type", "").lower()
        context.__dict__["objective_time"] = objectif.get("chrono_cible")
        context.__dict__["age"] = profile.get("age")

        # Stockage dans war_room (debug)
        context.war_room["inputs"] = {
            "mode": context.mode,
            "submode": context.submode,
            "objective_type": context.objective_type,
            "objective_time": context.objective_time,
            "age": context.age
        }

        # 1) Sélection scénario + famille via RG-00 (family_selector)
        scenario_id, model_family, scores = select_scenario_and_family(context)

        # War-room : on loggue les entrées + les scores
        context.war_room["scenario_id"] = scenario_id
        context.war_room["model_family"] = model_family
        context.war_room["scores"] = scores

        if scenario_id == "KO_SCENARIO":
            return InternalResult.error(
                message="Aucun scénario fonctionnel applicable",
                source="SCN_6",
                data={"war_room": context.war_room}
            )

        # Injection du model_family dans le contexte pour SCN_0g
        context.__dict__["model_family"] = model_family

        # ----------------------------------------------------
        # 4) Appel du moteur SOCLE SCN_0g
        # ----------------------------------------------------
        result = run_scn_0g(context)

        if not result.success:
            raise RuntimeError(f"SCN_0g a échoué : {result.message}")

        # ----------------------------------------------------
        # 5) Construction de la réponse
        # ----------------------------------------------------
        final_data = result.data or {}
        final_data["war_room"] = context.war_room

        return InternalResult.ok(
            data=final_data,
            source="SCN_6",
            message="Séance générée avec SCN_0g via SCN_6"
        )

    except Exception as e:
        logger.exception("[SCN_6] Exception")
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
