# scenarios/agregateur/adaptation_engine.py

from typing import Dict, Any


def compute_adaptation(run_context: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Calcule une adaptation simple à partir du run_context.
    Retourne None si aucune adaptation n'est requise.
    """

    adaptive = run_context.get("adaptive_context")
    if not adaptive:
        return None

    perceived_state = adaptive.get("perceived_state")

    # Cas 1 : fatigue → protection
    if perceived_state == "fatigued":
        return {
            "inputs": adaptive,
            "rules_applied": ["RG_ADP_001_FATIGUE_PROTECT"],
            "outcome": {
                "volume_factor": 0.8,
                "intensity_cap": "EF_ONLY",
                "target_type_override": "E",
            },
        }

    # Cas par défaut : neutral → no-op explicite
    return {
        "inputs": adaptive,
        "rules_applied": ["RG_ADP_010_NEUTRAL_STABILITY"],
        "outcome": {
            "volume_factor": 1.0,
            "intensity_cap": "AS_PLANNED",
            "target_type_override": None,
        },
    }
