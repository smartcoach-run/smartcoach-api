# scenarios/agregateur/slot_generator.py

from typing import Dict, Any


def generate_slot_session(
    slot: Dict[str, Any],
    profile: Dict[str, Any],
    objective: Dict[str, Any] | None = None,
    adaptation: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Génère une séance simple (EF) à partir du slot et du profil.
    """

    # Base duration (simple règle V1)
    base_duration = 50

    # Ajustement niveau (ultra simple)
    level = profile.get("level", "").lower()
    if level in ["debutant", "reprise"]:
        base_duration = 40
    elif level in ["intermediaire", "intermédiaire"]:
        base_duration = 50
    elif level in ["avance", "confirmé"]:
        base_duration = 60

    # Application adaptation (si présente)
    volume_factor = 1.0
    if adaptation:
        volume_factor = adaptation.get("outcome", {}).get("volume_factor", 1.0)

    duration = int(base_duration * volume_factor)

    # Séance EF minimale
    session = {
        "title": "Séance Endurance fondamentale",
        "date": slot.get("date"),
        "duration_min": duration,
        "intensity_tags": ["E"],
        "steps": [
            {
                "label": "Endurance fondamentale",
                "type": "E",
                "duration_min": duration,
            }
        ],
    }

    return session
