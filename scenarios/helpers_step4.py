from typing import Dict, Any, List
from utils.logging import log_info

DAYS_ORDER = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def build_step4_running(step3: Dict[str, Any]) -> Dict[str, Any]:
    """
    Étape 4 – Construction du plan (semaines + mapping phases)
    """

    # Sécurité : champs attendus
    plan_distance = step3.get("plan_distance")
    plan_nb_semaines = step3.get("plan_nb_semaines", 0)
    jours_retenus: List[str] = step3.get("jours_retenus", [])
    phases: List[Dict[str, Any]] = step3.get("phases", [])

    # Jours relatifs → lundi=1...dimanche=7
    jours_relatifs = {d: DAYS_ORDER.index(d) + 1 for d in jours_retenus if d in DAYS_ORDER}

    log_info(
        f"STEP4/Running → distance={plan_distance}, nb_semaines={plan_nb_semaines}, "
        f"jours_retenus={jours_retenus}, jours_relatifs={jours_relatifs}",
        module="SCN_1",
    )

    # Sécurité
    if not plan_distance or plan_nb_semaines <= 0:
        return {
            "status": "error",
            "reason": "plan_nb_semaines <= 0",
            "plan_distance": plan_distance,
            "plan_nb_semaines": plan_nb_semaines,
            "jours_retenus": jours_retenus,
            "jours_relatifs": jours_relatifs,
            "weeks": [],
        }

    # ——————————————————————————————————————
    # Construire toutes les semaines du plan
    # ——————————————————————————————————————
    weeks: List[Dict[str, Any]] = []

    # Récupérer les phases triées par ordre
    phases_sorted = sorted(phases, key=lambda p: p.get("ordre_phase", 0))

    # Construire une liste de mapping semaine → phase
    semaine_to_phase_index = {}

    for ph_index, ph in enumerate(phases_sorted, start=1):
        sem_deb = ph.get("semaine_debut", 1)
        sem_fin = ph.get("semaine_fin", 1)
        for s in range(sem_deb, sem_fin + 1):
            semaine_to_phase_index[s] = ph_index - 1  # index dans phases_sorted

    # ——————————————————————————————————————
    # Génération finale des semaines
    # ——————————————————————————————————————
    for s in range(1, plan_nb_semaines + 1):

        # Déterminer phase
        if s in semaine_to_phase_index:
            ph = phases_sorted[semaine_to_phase_index[s]]
            phase_info = {
                "phase": ph.get("phase_cle"),
                "phase_index": semaine_to_phase_index[s] + 1,
                "phase_distance": ph.get("distance"),
            }
        else:
            phase_info = {
                "phase": None,
                "phase_index": None,
                "phase_distance": None,
            }

        # Construire slots
        slots = [
            {
                "jour": j,
                "jour_relatif": jours_relatifs.get(j),
            }
            for j in jours_retenus
        ]

        weeks.append({
            "semaine": s,
            **phase_info,
            "slots": slots,
        })

    return {
        "status": "ok",
        "plan_distance": plan_distance,
        "plan_nb_semaines": plan_nb_semaines,
        "jours_retenus": jours_retenus,
        "jours_relatifs": jours_relatifs,
        "weeks": weeks,
    }
