# scenarios/socle/scn_0b.py

from core.internal_result import InternalResult
from core.utils.logger import log_info, log_warning, log_error, log_debug


# Ordre canonique des jours pour tous les usages
ORDERED_DAYS = [
    "Lundi", "Mardi", "Mercredi", "Jeudi",
    "Vendredi", "Samedi", "Dimanche"
]


def sort_days(days: list) -> list:
    """Trie les jours suivant ORDERED_DAYS."""
    return sorted(days, key=lambda x: ORDERED_DAYS.index(x)) if days else []


def run_scn_0b(jours_user_raw, jours_proposes, jours_min, jours_max) -> InternalResult:
    """
    SOCLE pur — optimisation des jours :

    Entrées :
      - jours_user_raw : liste jours sélectionnés Fillout
      - jours_proposes : liste jours recommandés via référentiel
      - jours_min      : entier min du référentiel
      - jours_max      : entier max du référentiel

    Sorties :
      InternalResult.ok( data={ ... } )
    """

    log_info("SCN_0b → optimisation des jours (SOCLE)", module="APP")

    try:
        # Conversion défensive
        if isinstance(jours_proposes, list) and len(jours_proposes) == 1 and isinstance(jours_proposes[0], list):
            jours_proposes = jours_proposes[0]

        if isinstance(jours_min, list):
            jours_min = jours_min[0]

        if isinstance(jours_max, list):
            jours_max = jours_max[0]

        # Debug
        log_debug(f"jours_user_raw  = {jours_user_raw}", module="SCN_0b")
        log_debug(f"jours_proposes  = {jours_proposes}", module="SCN_0b")
        log_debug(f"jours_min       = {jours_min}", module="SCN_0b")
        log_debug(f"jours_max       = {jours_max}", module="SCN_0b")

        # Vérifs type
        if not isinstance(jours_user_raw, list):
            return InternalResult.error("jours_user_raw doit être une liste", source="SCN_0b")

        if not isinstance(jours_proposes, list):
            return InternalResult.error("jours_proposes doit être une liste", source="SCN_0b")

        if not isinstance(jours_min, int):
            return InternalResult.error("jours_min doit être un entier", source="SCN_0b")

        if not isinstance(jours_max, int):
            return InternalResult.error("jours_max doit être un entier", source="SCN_0b")

        # ------------------------------------------------------------------
        # 1. Cas trivial : l’utilisateur a choisi assez de jours
        # ------------------------------------------------------------------
        nb_user = len(jours_user_raw)

        if nb_user >= jours_min:
            jours_final = sort_days(jours_user_raw)
            return InternalResult.ok(
                data={
                    "jours_final": jours_final,
                    "message": "Saisie utilisateur conservée",
                    "source_logic": "user_ok"
                },
                source="SCN_0b"
            )

        # ------------------------------------------------------------------
        # 2. Cas : trop peu de jours → compléter avec les jours proposés
        # ------------------------------------------------------------------
        jours_final = list(jours_user_raw)

        for j in jours_proposes:
            if j not in jours_final:
                jours_final.append(j)
            if len(jours_final) >= jours_min:
                break

        jours_final = sort_days(jours_final)

        return InternalResult.ok(
            data={
                "jours_final": jours_final,
                "message": "Jours complétés via référentiel",
                "source_logic": "autocompleted"
            },
            source="SCN_0b"
        )

    except Exception as e:
        log_error(f"SCN_0b → Exception : {e}", module="SCN_0b")
        return InternalResult.error(
            f"Erreur interne SCN_0b : {e}",
            source="SCN_0b"
        )
