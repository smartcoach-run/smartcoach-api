import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("ROOT")


class BABEngineMVP:
    """
    Moteur minimaliste BAB (Best Available Block) pour l'agrégation de séances.
    Version MVP améliorée avec prise en compte des phases fournies par SCN_6.
    """

    ENGINE_VERSION = "1.0.0-mvp"

    def __init__(self, candidates_repo):
        self.candidates_repo = candidates_repo

    # -------------------------------------------------------
    # SELECTION DES SEANCES
    # -------------------------------------------------------
    def compute_score(self, candidate: Dict[str, Any], run_context: Dict[str, Any]) -> float:
        """
        Score simple basé sur : intensité, durée, compatibilité phase.
        Version A (basique).
        """

        profile = run_context.get("profile", {})
        objectif = run_context.get("objectif", {})
        slot = run_context.get("slot", {})

        # Intensité du modèle
        tags = candidate.get("intensity_tags", [])
        is_easy = "E" in tags

        # Règles de phase
        slot_phase = slot.get("phase")
        phase_rules = objectif.get("phases", {})
        phase_params = phase_rules.get(slot_phase, {})

        # Pondération simple
        base = 50
        if is_easy:
            base += 5

        # Bonus si la séance matche le type d'allure
        seance_type = phase_params.get("allure_dominante")
        if seance_type and seance_type in tags:
            base += 5

        return float(base)

    # -------------------------------------------------------
    # MOTEUR PRINCIPAL
    # -------------------------------------------------------
    def run(self, run_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Moteur BAB : sélectionne la meilleure séance candidate.
        """

        logger.info("[BAB_ENGINE_MVP] run_context.mode=%s", run_context.get("mode"))

        # -------------------------
        # Extraction du contexte
        # -------------------------
        profile = run_context.get("profile", {})
        objectif = run_context.get("objectif", {})
        slot = run_context.get("slot", {})
        historique = run_context.get("historique", [])
        record_id = run_context.get("record_id")
        slot_id = run_context.get("slot_id")
        mode = run_context.get("mode", "ondemand")

        # Phase
        slot_phase = slot.get("phase")
        phase_rules = objectif.get("phases", {})
        current_phase_params = phase_rules.get(slot_phase, {})

        logger.info("[BAB_ENGINE_MVP] slot=%s", slot)
        logger.info("[BAB_ENGINE_MVP] Phase rules available: %s", list(phase_rules.keys()))
        logger.info("[BAB_ENGINE_MVP] Using phase params=%s", current_phase_params)

        # -------------------------
        # Récupération des candidats
        # -------------------------
        candidates = self.candidates_repo.list_all()

        if not candidates:
            raise Exception("Aucun modèle de séance trouvé dans candidates_repo")

        # -------------------------
        # Sélection du meilleur candidat
        # -------------------------
        best = None
        best_score = None

        for candidate in candidates:
            score = self.compute_score(candidate, run_context)
            if best_score is None or score > best_score:
                best = candidate
                best_score = score

        logger.info("[BAB_ENGINE_MVP] Best candidate=%s (score=%s)", best.get("code"), best_score)

        # -------------------------
        # Construction de la séance
        # -------------------------
        session = {
            "session_id": f"sess_{slot.get('date')}_{slot_id}",
            "slot_id": slot_id,
            "plan_id": None,
            "user_id": profile.get("user_id", "unknown"),
            "title": best.get("title"),
            "description": best.get("description", ""),
            "date": slot.get("date"),
            "phase": slot_phase,
            "type": slot.get("type"),
            "duration_min": best.get("duration_min"),
            "distance_km": best.get("distance_km"),
            "intensity_tags": best.get("intensity_tags", []),
            "steps": best.get("steps", []),
            "war_room": {
                "level": "soft",
                "alerts": [],
                "notes": [
                    f"Score séance modéré ({best_score})."
                ]
            },
            "metadata": {
                "generated_at": run_context.get("generated_at"),
                "mode": mode,
                "engine_version": self.ENGINE_VERSION,
                "socle_version": "SCN_0g",
            },
        }

        logger.info("[BAB_ENGINE_MVP] Phase context = %s", {
            "phase": slot_phase,
            "seance_type": current_phase_params.get("allure_dominante"),
            "volume_target": current_phase_params.get("duree_min"),
            "intensity_target": [current_phase_params.get("allure_dominante")],
            "distance_target": current_phase_params.get("distance_min"),
            "charge_cible": current_phase_params.get("charge_cible"),
        })

        return session
