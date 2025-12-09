# smartcoach_api/scenarios/agregateur/scn_6.py
# ============================================================
# SCN_6 : Agrégation finale du plan, génération structure JSON
# Moteur SmartCoach Engine (v2025-ST)
# ============================================================

from typing import Dict, Any, List

from fastapi import HTTPException

from core.internal_result import InternalResult
from core.context import SmartCoachContext

import logging

logger = logging.getLogger("SCN_6")


def _extract_phase_for_week(week_id: str, week_data: Dict[str, Any]) -> str:
    """Tente de récupérer la phase associée à une semaine.

    Priorité :
    1) week_data["phase"]
    2) phase du premier slot (slot["phase"])
    3) chaîne vide
    """
    if isinstance(week_data, dict):
        if week_data.get("phase"):
            return week_data["phase"]

        slots = week_data.get("slots") or []
        if slots and isinstance(slots, list):
            first = slots[0]
            if isinstance(first, dict) and first.get("phase"):
                return first["phase"]

    return ""


def build_plan_structure(context: SmartCoachContext) -> List[Dict[str, Any]]:
    """Construit la structure finale du plan à partir des slots enrichis.

    On part du principe que :
    - SCN_0d / SCN_0e ont généré `context.slots_by_week`
      sous la forme : { "S1": {"slots": [...]}, "S2": {...}, ... }
    - SCN_2 a calculé les cibles (type_allure, etc.)
    - SCN_3 a injecté les modèles Airtable (modele, description, duree, categorie)
    """
    slots_by_week = getattr(context, "slots_by_week", {}) or {}

    if not isinstance(slots_by_week, dict) or not slots_by_week:
        logger.warning("[SCN_6] Aucun slot disponible dans context.slots_by_week.")
        return []

    # On trie les semaines par numéro (S1, S2, ..., S10)
    def _week_sort_key(week_key: str) -> int:
        try:
            return int(str(week_key).lstrip("S"))
        except Exception:
            return 0

    plan: List[Dict[str, Any]] = []

    for idx, (week_id, week_data) in enumerate(
        sorted(slots_by_week.items(), key=lambda kv: _week_sort_key(kv[0])),
        start=1,
    ):
        raw_slots: List[Dict[str, Any]] = []

        if isinstance(week_data, dict):
            raw_slots = week_data.get("slots") or []
        elif isinstance(week_data, list):
            # Compat : si jamais week_data est directement une liste de slots
            raw_slots = week_data
        else:
            raw_slots = []

        # Tri des séances par jour_relatif
        seances_triees = sorted(
            [s for s in raw_slots if isinstance(s, dict)],
            key=lambda s: s.get("jour_relatif", 0),
        )

        seances: List[Dict[str, Any]] = []

        for sess in seances_triees:
            slot_id = sess.get("slot_id")
            jour = sess.get("jour")
            jour_relatif = sess.get("jour_relatif")

            # Type d’allure prioritaire :
            # 1) ce que SCN_3 a éventuellement mis (clé courte)
            # 2) type_seance_cle / categorie_seance (hérités de SCN_2)
            type_allure = (
                sess.get("type_allure")
                or sess.get("type_seance_cle")
                or sess.get("categorie_seance")
                or ""
            )

            modele = sess.get("modele") or "Séance non trouvée"
            categorie = (
                sess.get("categorie")
                or sess.get("categorie_smartcoach")
                or sess.get("categorie_seance")
                or type_allure
                or ""
            )

            duree = sess.get("duree")
            description = sess.get("description") or ""

            seances.append(
                {
                    "slot_id": slot_id,
                    "jour": jour,
                    "jour_relatif": jour_relatif,
                    "type_allure": type_allure,
                    "modele": modele,
                    "categorie": categorie,
                    "duree": duree,
                    "description": description,
                }
            )

        phase = _extract_phase_for_week(week_id, week_data)

        plan.append(
            {
                "semaine": idx,
                "phase": phase,
                "seances": seances,
            }
        )

    return plan


def run_plan_aggregator(context: SmartCoachContext) -> InternalResult:
    """Scénario SCN_6 : agrégation finale du plan.

    - Ne lit plus directement Airtable (les modèles sont déjà injectés en SCN_3)
    - Se contente de transformer `context.slots_by_week` en structure `plan`
      prête à être renvoyée par l’API ou utilisée pour la génération HTML.
    """
    try:
        plan = build_plan_structure(context)

        return InternalResult.ok(
            message="SCN_6 terminé avec succès (Version STABLE)",
            data={"plan": plan},
        )

    except Exception as e:
        logger.exception(f"[SCN_6] Erreur inattendue : {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur dans SCN_6 : {e}",
        )
