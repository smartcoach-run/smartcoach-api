# smartcoach_api/scenarios/agregateur/scn_6.py
# ============================================================
# SCN_6 : Agrégation finale du plan, génération HTML + structure
# Moteur SmartCoach Engine (v2025)
# ============================================================

from typing import Dict, Any, List
from core.internal_result import InternalResult
from core.context import SmartCoachContext
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES
from fastapi import HTTPException

# ===== IMPORT MAPPING =====
from utils.session_types_utils import map_record_to_session_type


# ============================================================
# Sélection du template normalisé
# ============================================================
def find_template(
    templates: List[Dict[str, Any]],
    phase_label: str,
    objectif: str,
    allure: str
):
    """
    Recherche d’un template via les champs normalisés :
      - phase_ids      (Phase cible)
      - objectifs      (Objectif : 10K, HM, M…)
      - slot_types     (E, EF, I, AS10...)
    """

    matching = []

    for tpl in templates:
        phases = tpl.get("phase_ids", [])
        objectifs = tpl.get("objectifs", [])
        types = tpl.get("slot_types", [])

        # Phase match
        if phase_label not in phases:
            continue

        # Objectif (ex : "10K")
        if objectif not in objectifs:
            continue

        # Type séance (court)
        if allure not in types:
            continue

        matching.append(tpl)

    if not matching:
        return None

    # Pour l’instant → premier match
    return matching[0]


# ============================================================
# Construction du JSON final semaine → séances
# ============================================================
def build_plan_structure(context: SmartCoachContext, templates: List[Dict[str, Any]]):

    # 1) Données de base du contexte
    phases = context.phases or []
    sessions = context.get("sessions_targets") or []

    # Objectif normalisé : on privilégie la version normalisée
    objectif = (
        getattr(context, "objectif_normalise", None)
        or getattr(context, "objectif", None)
        or ""
    )

    # 2) Index des phases par semaine : {1: "Prépa générale", 2: "Spécifique", ...}
    phase_by_week = {}
    for p in phases:
        semaine = p.get("semaine")
        if semaine is not None:
            phase_by_week[semaine] = p.get("phase")

    # 3) Regroupement des séances par semaine : {1: [sess1, sess2], 2: [...], ...}
    sessions_by_week: Dict[int, List[Dict[str, Any]]] = {}
    for sess in sessions:
        semaine = sess.get("semaine")
        if semaine is None:
            continue
        sessions_by_week.setdefault(semaine, []).append(sess)

    plan: List[Dict[str, Any]] = []

    # 4) Construction du plan, semaine par semaine (ordre croissant)
    for semaine in sorted(sessions_by_week.keys()):
        phase_name = phase_by_week.get(semaine, "")

        block = {
            "semaine": semaine,
            "phase": phase_name,
            "seances": [],
        }

        # On trie les séances dans la semaine par jour_relatif pour un rendu propre
        seances_semaine = sorted(
            sessions_by_week[semaine],
            key=lambda s: s.get("jour_relatif", 0),
        )

        for sess in seances_semaine:
            slot_id = sess.get("slot_id")
            jour = sess.get("jour")
            jour_relatif = sess.get("jour_relatif")

            # Type court pour le matching template (EF, I, AS10, ...)
            allure = (
                sess.get("type_seance_cle")
                or sess.get("categorie_seance")
                or ""
            )

            template = find_template(
                templates=templates,
                phase_label=phase_name or "",
                objectif=objectif,
                allure=allure,
            )

            if template:
                block["seances"].append(
                    {
                        "slot_id": slot_id,
                        "jour": jour,
                        "jour_relatif": jour_relatif,
                        "type_allure": allure,
                        "categorie": template.get("categorie"),
                        "modele": template.get("nom"),
                        "duree": template.get("duree_min"),
                        "description": template.get("description"),
                    }
                )
            else:
                block["seances"].append(
                    {
                        "slot_id": slot_id,
                        "jour": jour,
                        "jour_relatif": jour_relatif,
                        "type_allure": allure,
                        "modele": "Séance non trouvée",
                        "categorie": allure,
                        "duree": None,
                        "description": "Aucun modèle correspondant dans Airtable.",
                    }
                )

        plan.append(block)

    return plan

# ============================================================
# SCN_6 — Entrée principale
# ============================================================
def run_scn_6(context: SmartCoachContext) -> InternalResult:
    """
    Agrégation finale :
      - On lit Airtable (Séances types)
      - On normalise (map_record_to_session_type)
      - On génère la structure finale du plan
    """

    try:
        service = AirtableService()

        raw_templates = service.list_all(ATABLES.SEANCES_TYPES)

        templates = [map_record_to_session_type(rec) for rec in raw_templates]

        plan = build_plan_structure(context, templates)

        return InternalResult.ok(
            message="SCN_6 terminé avec succès (Version STABLE)",
            data={"plan": plan},
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur dans SCN_6 : {e}"
        )
