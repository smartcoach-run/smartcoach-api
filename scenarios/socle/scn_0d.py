"""
SCN_0d — Génération de la Structure (Slots)
SOCLE v2025-11
"""
import logging
from core.utils.logger import log_info, log_error, log_warning, log_debug

log = logging.getLogger("SCN_0d")

def run_scn_0d(jours_retenus, jours_relatifs, nb_semaines):
    """
    SOCLE — pure function
    Génère la structure brute (slots) semaine par semaine.

    Inputs :
        jours_retenus  = ["Lundi", "Mercredi", "Dimanche"]
        jours_relatifs = {"Lundi":1, "Mercredi":2, "Dimanche":3}
        nb_semaines    = 7

    Output :
        [
          {
            "semaine": 1,
            "slots": [
                {"jour":"Lundi","jour_relatif":1,"slot_id":"S1-J1"},
                ...
            ]
          },
          ...
        ]
    """

    log.info(f"SCN_0d → Génération structure brute ({nb_semaines} semaines)")

    structure = []

    try:
        for semaine in range(1, nb_semaines + 1):

            slots = []

            for jour in jours_retenus:
                position = jours_relatifs[jour]
                slot_id = f"S{semaine}-J{position}"

                slots.append({
                    "jour": jour,
                    "jour_relatif": position,
                    "slot_id": slot_id
                })

            structure.append({
                "semaine": semaine,
                "slots": slots
            })

        log.info("SCN_0d → Structure générée avec succès")

    except Exception as e:
        log.error(f"SCN_0d → ERREUR : {e}")
        raise

    return structure
