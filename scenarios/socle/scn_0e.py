"""
SCN_0e — Application des phases
SOCLE v2025-11
"""
import logging
from core.utils.logger import log_info, log_error, log_warning, log_debug, get_logger

log = logging.getLogger("SCN_0e")

def run_scn_0e(structure_slots, nb_semaines):
    """
    Ajoute l'information de phase à chaque semaine d'une structure brute.

    Inputs :
        structure_slots = [
            { "semaine": 1, "slots": [...] },
            ...
        ]
        nb_semaines = 7

    Output :
        [
          {
            "semaine": 1,
            "phase": "PHASE 1 — Mise en route",
            "slots": [...]
          },
          ...
        ]
    """

    log_info(f"SCN_0e → Attribution des phases (nb_semaines={nb_semaines})")

    # Sélection du modèle de phases
    phases = _compute_phase_slices(nb_semaines)

    result = []

    try:
        for week_data in structure_slots:
            semaine = week_data["semaine"]

            phase_name, phase_index = _get_phase_for_week(semaine, phases)

            result.append({
                "semaine": semaine,
                "phase": phase_name,
                "phase_index": phase_index,
                "slots": week_data["slots"]
            })

        log.info("SCN_0e → Phases appliquées avec succès")

    except Exception as e:
        log.error(f"SCN_0e → ERREUR : {e}")
        raise

    return result


# -------------------------------------------------------------------
# 🔧 Découpage des phases SOCLE (géométrique, sans métier)
# -------------------------------------------------------------------

def _compute_phase_slices(nb_semaines):
    """
    Détermine les bornes des phases selon le nombre total de semaines.
    SOCLE — aucun métier.
    """

    if nb_semaines <= 8:
        # Plans courts (6–8 semaines)
        return [
            ("PHASE 1 — Mise en route", 1, 2),
            ("PHASE 2 — Développement", 3, nb_semaines - 1),
            ("PHASE 3 — Affûtage", nb_semaines, nb_semaines),
        ]

    elif nb_semaines <= 12:
        # Plan standard (9–12 semaines)
        p1 = int(nb_semaines * 0.25)
        p3 = int(nb_semaines * 0.25)
        p2 = nb_semaines - (p1 + p3)

        return [
            ("PHASE 1 — Base", 1, p1),
            ("PHASE 2 — Développement", p1 + 1, p1 + p2),
            ("PHASE 3 — Affûtage", nb_semaines - p3 + 1, nb_semaines),
        ]

    else:
        # Plans longs (13–20 semaines)
        p1 = int(nb_semaines * 0.30)
        p2 = int(nb_semaines * 0.50)
        remaining = nb_semaines - (p1 + p2)

        p3 = int(remaining * 0.75)
        p4 = remaining - p3

        return [
            ("PHASE 1 — Base", 1, p1),
            ("PHASE 2 — Construction", p1 + 1, p1 + p2),
            ("PHASE 3 — Spécifique", p1 + p2 + 1, p1 + p2 + p3),
            ("PHASE 4 — Affûtage", p1 + p2 + p3 + 1, nb_semaines),
        ]


def _get_phase_for_week(semaine, phase_slices):
    """
    Retourne (phase_name, phase_index) pour une semaine donnée.
    """
    for phase_name, start, end in phase_slices:
        if start <= semaine <= end:
            phase_index = semaine - start + 1
            return phase_name, phase_index

    # Fallback impossible théoriquement
    return "PHASE ? — Non défini", 1
