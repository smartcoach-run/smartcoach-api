# utils/training_days.py

from typing import List

DAY_MAP = {
    "lundi": 1,
    "mardi": 2,
    "mercredi": 3,
    "jeudi": 4,
    "vendredi": 5,
    "samedi": 6,
    "dimanche": 7,
}

def resolve_training_days(jours_final):
    """
    Accepte :
    - "Lundi,Mercredi,Vendredi"
    - ["Lundi", "Mercredi"]
    - [1, 3, 5]

    Retourne :
    - List[int] ISO 8601 : 1=lundi … 7=dimanche
    """

    if not jours_final:
        raise ValueError("jours_final vide ou non défini")

    # Cas 1 : string
    if isinstance(jours_final, str):
        jours = [j.strip() for j in jours_final.split(",") if j.strip()]

    # Cas 2 : liste
    elif isinstance(jours_final, list):
        jours = jours_final

    else:
        raise TypeError("jours_final doit être str ou list")

    resolved = []

    for j in jours:
        # Déjà numérique (ISO)
        if isinstance(j, int):
            if 1 <= j <= 7:
                resolved.append(j)
            else:
                raise ValueError(f"Jour invalide (int) : {j}")

        # String → mapping ISO
        elif isinstance(j, str):
            key = j.strip().lower()
            if key not in DAY_MAP:
                raise ValueError(f"Jour invalide dans jours_final : {j}")
            resolved.append(DAY_MAP[key])

        else:
            raise ValueError(f"Type de jour invalide : {j}")

    # normalisation ISO 1–7
    normalized = sorted(set(resolved))
    if not normalized:
        raise ValueError("jours_final vide après résolution")
    assert all(1 <= d <= 7 for d in normalized), "resolve_training_days must return ISO (1–7)"
    return normalized
