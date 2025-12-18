"""
SCN_0f — Construction du JSON final (structure-only)
SOCLE v2025-11
"""
import logging

from core.utils.logger import log_info, log_error, log_warning, log_debug

log = logging.getLogger("SCN_0f")

def run_scn_0f(
    record_id: str,
    mode: str,
    objectif: str,
    vdot: int,
    niveau: str,
    jours_retenus: list,
    nb_semaines: int,
    structure_phases: list,
    version_scenario: str = "2025-11",
    scenario_name: str = "SCN_1"
):
    """
    Assemble toutes les données déjà calculées par les SOCLE précédents
    pour construire le JSON final renvoyé par SCN_1.

    ⚠️ Ce SOCLE NE FAIT AUCUN CALCUL.
       Il assemble uniquement.

    Inputs :
        record_id          -> ID Airtable
        mode               -> Running / Kids / Hyrox / Vitalité
        objectif           -> Exemple : "10K"
        vdot               -> VDOT calculé par SCN_0c
        niveau             -> Niveau ajusté
        jours_retenus      -> Jours optimisés finaux
        nb_semaines        -> Durée du plan
        structure_phases   -> Structure complète SCN_0d + SCN_0e
        version_scenario   -> Identifiant version
        scenario_name      -> Nom du scénario fonctionnel appelant

    Output :
        JSON propre et contractuel, sans séances détaillées.
    """

    log_info("SCN_0f → Construction du JSON final (structure only)")

    try:
        json_final = {
            "version": version_scenario,
            "scenario": scenario_name,
            "record_id": record_id,
            "mode": mode,
            "objectif": objectif,
            "vdot": vdot,
            "niveau": niveau,
            "jours_retenus": jours_retenus,
            "nb_semaines": nb_semaines,
            "semaines": []
        }

        # Assemblage des semaines
        for item in structure_phases:
            semaine = item.get("semaine")
            phase = item.get("phase")
            phase_index = item.get("phase_index")
            slots = item.get("slots", [])

            json_final["semaines"].append({
                "semaine": semaine,
                "phase": phase,
                "phase_index": phase_index,
                "slots": [
                    {
                        "jour": slot.get("jour"),
                        "jour_relatif": slot.get("jour_relatif")
                    }
                    for slot in slots
                ]
            })

        log.info("SCN_0f → JSON final assemblé avec succès")

        return json_final

    except Exception as e:
        log.error(f"SCN_0f → ERREUR durant l'assemblage JSON : {e}")
        raise
