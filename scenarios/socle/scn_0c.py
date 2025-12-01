import logging
from core.utils.logger import log_info, log_debug
from core.internal_result import InternalResult

log = logging.getLogger("SCN_0c")

ORDERED_DAYS = [
    "Lundi", "Mardi", "Mercredi", "Jeudi",
    "Vendredi", "Samedi", "Dimanche"
]

def run_scn_0c(context, jours_final):

    try:
        objectif_norm = context.objectif_normalise
        niveau_norm = context.niveau_normalise
        cle_ref = context.cle_niveau_reference

        semaine_type = {
            "jours": {},
            "meta": {
                "objectif": objectif_norm,
                "niveau": niveau_norm,
                "nb_jours": len(jours_final),
                "cle_reference": cle_ref
            }
        }

        # Ordonnancement
        jours_ordonnes = [j for j in ORDERED_DAYS if j in jours_final]
        log.debug(f"Jours retenus (ordonnés) → {jours_ordonnes}", module="SCN_0c")

        if not jours_ordonnes:
            return InternalResult.make_error(
                "Erreur SCN_0c : aucun jour retenu après ordonnancement.",
                source="SCN_0c"
            )

        # Mapping jour -> clé modèle
        for jour in jours_ordonnes:
            semaine_type["jours"][jour] = {
                "cle_modele": cle_ref
            }

        log.info("SCN_0c → Semaine-type construite avec succès", module="SCN_0c")
        log.debug(f"Semaine-type → {semaine_type}", module="SCN_0c")

        return InternalResult.make_success(semaine_type)

    except Exception as e:
        return InternalResult.make_error(
            f"Erreur interne SCN_0c : {e}",
            source="SCN_0c"
        )
