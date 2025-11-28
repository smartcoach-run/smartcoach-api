# ============================================================
# SCN_0c – Construction de la semaine-type (SOCLE)
# ============================================================

from core.utils.logger import log_info, log_error, log_debug
from core.internal_result import InternalResult
from services.airtable_fields import ATFIELDS

# Pour l’ordre propre (Lundi → Dimanche)
ORDERED_DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def run_scn_0c(context, jours_final):
    """
    SCN_0c construit une structure propre de semaine-type :
    - Jours final retenus (déjà validés et optimisés par SCN_0b)
    - Clé modèle pour chaque jour (Airtable → champ Clé_niveau_reference)
    - Informations méta (objectif, niveau, nb_jours)

    IMPORTANT : 
    SCN_0c NE génère PAS les séances.
    Il prépare seulement la structure propre pour SCN_0d.
    """

    try:
        log_info("SCN_0c → Construction de la semaine-type", module="SCN_0c")

        fields = context.record.get("fields", {})

        # Champs nécessaires (provenant d'Airtable)
        try:
            objectif_norm = fields[ATFIELDS.COU_OBJECTIF_NORMALISE]
            niveau_norm = fields[ATFIELDS.COU_NIVEAU_NORMALISE]
            cle_ref = fields[ATFIELDS.COU_CLE_NIVEAU_REF]
        except KeyError as e:
            return InternalResult.error(
                f"Champ manquant dans SCN_0c : {e}",
                source="SCN_0c"
            )

        # ----------------------------
        # Préparation du mapping semaine-type
        # ----------------------------
        semaine_type = {
            "jours": {},
            "meta": {
                "objectif": objectif_norm,
                "niveau": niveau_norm,
                "nb_jours": len(jours_final),
                "cle_reference": cle_ref
            }
        }

        # ----------------------------
        # Ordonnancement propre
        # ----------------------------
        jours_ordonnes = [j for j in ORDERED_DAYS if j in jours_final]

        log_debug(f"Jours retenus (ordonnés) → {jours_ordonnes}", module="SCN_0c")

        # ----------------------------
        # Mapping "jour → clé modele"
        # (clé modèle = clé_niveau_reference)
        # ----------------------------
        for jour in jours_ordonnes:
            semaine_type["jours"][jour] = {
                "cle_modele": cle_ref
            }

        log_info("SCN_0c → Semaine-type construite avec succès", module="SCN_0c")
        log_debug(f"Semaine-type → {semaine_type}", module="SCN_0c")

        return InternalResult.ok(data=semaine_type, source="SCN_0c")

    except Exception as e:
        log_error(f"SCN_0c → Exception : {e}", module="SCN_0c")
        return InternalResult.error(str(e), source="SCN_0c")
