import logging
from itertools import combinations
from typing import List, Optional, Sequence, Tuple, Dict

from core.internal_result import InternalResult

logger = logging.getLogger("SCN_0b")

# Ordre canonique des jours
ORDERED_DAYS: List[str] = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
]

DAY_INDEX: Dict[str, int] = {d: i for i, d in enumerate(ORDERED_DAYS)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm_days(raw: Optional[Sequence[str]]) -> List[str]:
    """Normalise une liste de jours (liste, None, string…) en liste triée unique."""
    if not raw:
        return []
    if isinstance(raw, str):
        days = [raw]
    else:
        days = list(raw)

    # Filtrer uniquement les jours connus
    days = [d for d in days if d in DAY_INDEX]
    # Uniques + triés
    return sorted(set(days), key=lambda d: DAY_INDEX[d])


def _build_ranked_candidates(
    jours_user: List[str],
    jours_proposes: List[str],
) -> Tuple[List[str], List[str], List[str]]:
    """
    Construit les rangs :
    - rang 1 : jours_user (toujours conservés)
    - rang 2 : jours_proposes (hors rang 1)
    - rang 3 : jours restants de la semaine
    """
    set_user = set(jours_user)
    set_prop = set(jours_proposes) - set_user
    set_rest = set(ORDERED_DAYS) - set_user - set_prop

    rang1 = sorted(set_user, key=lambda d: DAY_INDEX[d])
    rang2 = sorted(set_prop, key=lambda d: DAY_INDEX[d])
    rang3 = sorted(set_rest, key=lambda d: DAY_INDEX[d])

    return rang1, rang2, rang3


def _diffs_for_combo(combo: List[str]) -> List[int]:
    """Retourne les écarts (en jours) entre jours adjacents dans la semaine."""
    indices = [DAY_INDEX[d] for d in combo]
    return [indices[i + 1] - indices[i] for i in range(len(indices) - 1)]


def _has_three_consecutive(diffs: List[int]) -> bool:
    """Vrai s'il existe une séquence de trois jours consécutifs (diffs = 1 puis 1)."""
    return any(diffs[i] == 1 and diffs[i + 1] == 1 for i in range(len(diffs) - 1))


def _respects_strict_spacing(
    combo: List[str],
    esp_min: int,
    esp_max: int,
) -> bool:
    """
    Version stricte :
    - aucun jour consécutif (diff == 1 interdit)
    - tous les écarts dans [esp_min, esp_max]
    """
    diffs = _diffs_for_combo(combo)
    if not diffs:
        return True

    for d in diffs:
        # Jours consécutifs interdits en mode "strict"
        if d == 1:
            return False
        if d < esp_min or d > esp_max:
            return False

    return True


def _respects_soft_spacing(
    combo: List[str],
) -> bool:
    """
    Version "souple" : pas de 3 jours consécutifs,
    mais on ne bloque pas sur les valeurs esp_min / esp_max.
    On peut donc accepter une paire consécutive en fallback.
    """
    diffs = _diffs_for_combo(combo)
    if not diffs:
        return True
    return not _has_three_consecutive(diffs)


def _spacing_penalty(
    combo: List[str],
    esp_min: int,
    esp_max: int,
    jours_user: List[str],
    jours_proposes: List[str],
) -> Tuple[int, int, int]:
    """
    Calcule un score de pénalité pour comparer deux combinaisons en fallback.

    Plus le score est petit, meilleure est la solution.
    On combine :
    - violation de [esp_min, esp_max]
    - présence de jours consécutifs
    - utilisation de jours hors référentiel (rang 3)
    """
    diffs = _diffs_for_combo(combo)
    penalty = 0

    # Pénalités d'espacement
    for d in diffs:
        if d < esp_min:
            penalty += (esp_min - d) * 3  # gros malus si trop rapproché
        elif d > esp_max:
            penalty += (d - esp_max) * 2  # malus si trop éloigné

        if d == 1:
            # léger malus pour les jours consécutifs (acceptés seulement en fallback)
            penalty += 1

    if _has_three_consecutive(diffs):
        penalty += 100  # gros malus pour 3 jours consécutifs

    set_user = set(jours_user)
    set_prop = set(jours_proposes)
    set_rest = set(combo) - set_user - set_prop
    nb_rest = len(set_rest)

    # On préfère utiliser les jours proposés plutôt que les jours "restants"
    penalty += nb_rest * 2

    # Clés secondaires pour départager les égalités :
    # - moins de jours "restants"
    # - puis combinaison la plus "compacte" (somme des écarts)
    total_span = sum(diffs) if diffs else 0

    return penalty, nb_rest, total_span


# ---------------------------------------------------------------------------
# Fonction principale SCN_0b
# ---------------------------------------------------------------------------

def run_scn_0b(
    jours_user_raw: Optional[Sequence[str]],
    jours_proposes: Optional[Sequence[str]],
    jours_min: Optional[int],
    jours_max: Optional[int],
    esp_min: Optional[int],
    esp_max: Optional[int],
) -> InternalResult:
    """
    SCN_0b : optimisation des jours
    - conserve toujours les jours saisis par l'utilisateur
    - privilégie les jours_proposés Airtable
    - complète avec les autres jours si nécessaire
    - applique espacement_min / espacement_max autant que possible
    """

    try:
        # Normalisation des entrées
        jours_user = _norm_days(jours_user_raw)
        jours_proposes_norm = _norm_days(jours_proposes)

        # Defaults raisonnables si non définis
        if esp_min is None:
            esp_min = 1
        if esp_max is None or esp_max < esp_min:
            esp_max = 7

        # Log de debug
        logger.debug("SCN_0b ┊ esp_min = %s, esp_max = %s", esp_min, esp_max)
        logger.debug("SCN_0b ┊ jours_user_raw  = %s", list(jours_user_raw or []))
        logger.debug("SCN_0b ┊ jours_proposes  = %s", list(jours_proposes_norm))
        logger.debug("SCN_0b ┊ jours_min       = %s", jours_min)
        logger.debug("SCN_0b ┊ jours_max       = %s", jours_max)

        # Construction des rangs
        rang1, rang2, rang3 = _build_ranked_candidates(jours_user, jours_proposes_norm)

        # Détermination du nb de jours cible
        nb_user = len(rang1)
        nb_total_possible = len(
            sorted(set(rang1 + rang2 + rang3), key=lambda d: DAY_INDEX[d])
        )

        if jours_min is None:
            jours_min = max(1, nb_user)
        if jours_max is None:
            jours_max = max(jours_min, nb_user)

        # On veut au moins tous les jours user, mais pas plus que jours_max,
        # ni plus que le nombre de jours dispo dans la semaine
        target = max(jours_min, nb_user)
        target = min(target, jours_max, nb_total_possible)

        # Pool de candidats (rang 1 + 2 + 3, dans l'ordre de la semaine)
        candidats = sorted(
            set(rang1 + rang2 + rang3),
            key=lambda d: DAY_INDEX[d],
        )

        # Si on n'a pas assez de jours pour le target, on réduit le target
        if target > len(candidats):
            target = len(candidats)

        # Si on n'a toujours rien (cas pathologique), on renvoie les jours user
        if target == 0:
            return InternalResult.ok(
                data={
                    "jours_result": {"jours_valides": []},
                    "esp_min": esp_min,
                    "esp_max": esp_max,
                },
                source="SCN_0b",
            )

        # Génération des combinaisons
        set_user = set(rang1)
        autres = [d for d in candidats if d not in set_user]
        nb_a_choisir = max(0, target - len(rang1))

        all_combos: List[List[str]] = []
        if nb_a_choisir == 0:
            all_combos = [sorted(rang1, key=lambda d: DAY_INDEX[d])]
        else:
            for subset in combinations(autres, nb_a_choisir):
                combo = sorted(list(set(rang1).union(subset)), key=lambda d: DAY_INDEX[d])
                if len(combo) == target:
                    all_combos.append(combo)

        if not all_combos:
            # Fallback extrême : au cas où, on renvoie union simple
            fallback = sorted(set(rang1 + rang2 + rang3)[:target], key=lambda d: DAY_INDEX[d])
            return InternalResult.ok(
                data={
                    "jours_result": {"jours_valides": fallback},
                    "esp_min": esp_min,
                    "esp_max": esp_max,
                },
                source="SCN_0b",
            )

        # --------------------------------------------------------------
        # Étape 1 : solutions strictes (pas de jours consécutifs,
        #           esp_min ≤ diff ≤ esp_max)
        # --------------------------------------------------------------
        strict_candidates = [
            combo for combo in all_combos if _respects_strict_spacing(combo, esp_min, esp_max)
        ]

        if strict_candidates:
            # On choisit la meilleure selon la pénalité
            best = min(
                strict_candidates,
                key=lambda c: _spacing_penalty(c, esp_min, esp_max, rang1, rang2),
            )
            logger.debug("SCN_0b ┊ combo choisie (strict) : %s", best)
            return InternalResult.ok(
                data={
                    "jours_result": {"jours_valides": best},
                    "esp_min": esp_min,
                    "esp_max": esp_max,
                },
                source="SCN_0b",
            )

        # --------------------------------------------------------------
        # Étape 2 : solutions "souples" (pas 3 jours consécutifs)
        # --------------------------------------------------------------
        soft_candidates = [combo for combo in all_combos if _respects_soft_spacing(combo)]

        if soft_candidates:
            best = min(
                soft_candidates,
                key=lambda c: _spacing_penalty(c, esp_min, esp_max, rang1, rang2),
            )
            logger.debug("SCN_0b ┊ combo choisie (soft) : %s", best)
            return InternalResult.ok(
                data={
                    "jours_result": {"jours_valides": best},
                    "esp_min": esp_min,
                    "esp_max": esp_max,
                },
                source="SCN_0b",
            )

        # --------------------------------------------------------------
        # Étape 3 : fallback dégradé : meilleure combinaison possible
        # --------------------------------------------------------------
        best = min(
            all_combos,
            key=lambda c: _spacing_penalty(c, esp_min, esp_max, rang1, rang2),
        )
        logger.debug("SCN_0b ┊ combo choisie (fallback) : %s", best)

        return InternalResult.ok(
            data={
                "jours_result": {"jours_valides": best},
                "esp_min": esp_min,
                "esp_max": esp_max,
            },
            source="SCN_0b",
        )

    except Exception as e:
        logger.exception("SCN_0b → Exception : %s", e)
        return InternalResult.make_error(
            message=f"Erreur dans SCN_0b : {e}",
            source="SCN_0b",
        )
