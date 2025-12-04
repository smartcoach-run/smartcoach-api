# ============================================================
# SCN_0d — Génération des slots bruts (v2025 stable)
# Compatibilité : SCN_1 (appel direct) + SCN_2 (itération)
# Entrée : jours_retenus (liste), jours_relatifs (dict), nb_semaines (int)
# Sortie : dict { "S1": {"slots": [...]}, "S2": {"slots": [...]} }
# Pas d’InternalResult ici — SCN_1 gère déjà tout.
# ============================================================

from core.utils.logger import get_logger
log = get_logger("SCN_0d")

def run_scn_0d(jours_retenus, jours_relatifs, nb_semaines):
    """
    Génère les slots bruts (Sx-Jy) pour les semaines/ jours retenus.

    Exemple de sortie :
    {
        "S1": {
            "slots": [
                {"slot_id": "S1-J1", "jour": "Mardi", "jour_relatif": 1},
                {"slot_id": "S1-J2", "jour": "Jeudi", "jour_relatif": 2},
                {"slot_id": "S1-J3", "jour": "Dimanche", "jour_relatif": 3},
            ]
        },
        "S2": { ... }
    }
    """
    if not jours_retenus or not jours_relatifs or nb_semaines <= 0:
        return {}

    slots_by_week = {}

    # Pour chaque semaine
    for semaine in range(1, nb_semaines + 1):
        week_id = f"S{semaine}"
        slots = []

        # Pour chaque jour choisi par l'utilisateur
        for jour in jours_retenus:
            rel = jours_relatifs.get(jour, None)
            if rel is None:
                continue

            slot_id = f"{week_id}-J{rel}"

            slots.append({
                "slot_id": slot_id,
                "jour": jour,
                "jour_relatif": rel
            })

        slots_by_week[week_id] = {"slots": slots}

    log.info(f"[SCN_0d] OUTPUT slots_by_week = {slots_by_week}")

    return slots_by_week
