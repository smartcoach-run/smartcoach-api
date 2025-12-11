import logging
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger("ROOT")

# Score minimal pour considérer qu'un scénario est applicable
MIN_SCORE = 60


# ---------- Helpers lecture contexte ----------

def _get_attr(ctx: Any, name: str, default: Any = None) -> Any:
    """Helper robuste: évite les AttributeError."""
    return getattr(ctx, name, default)


# ---------- Règles de scoring pour chaque scénario ----------

def _score_sc_001(ctx: Any) -> int:
    """
    SC-001 : Homme 40-55 ans, running, reprise, marathon, objectif 3h45.
    Retourne un score 0-100.
    """

    mode = _get_attr(ctx, "mode")
    submode = _get_attr(ctx, "submode")
    obj_type = _get_attr(ctx, "objective_type")
    obj_time = _get_attr(ctx, "objective_time")
    age = _get_attr(ctx, "age")

    # Conditions strictes pour l'instant → score binaire 0 ou 100
    if (
        mode == "running"
        and submode == "reprise"
        and obj_type == "marathon"
        and obj_time in ("3:45", "3:45:00")
        and (age is None or 40 <= age <= 55)
    ):
        return 100

    return 0


# ---------- Table des scénarios déclarés ----------

ScenarioRule = Dict[str, Any]

SCENARIO_RULES: List[ScenarioRule] = [
    {
        "id": "SC-001",
        "family": "MARA_REPRISE_Q1",
        "score_fn": _score_sc_001,
    },
    # Plus tard :
    # {
    #   "id": "SC-002",
    #   "family": "XXX",
    #   "score_fn": _score_sc_002,
    # },
]


# ---------- Sélection principale (RG-00) ----------

def select_scenario_and_family(ctx: Any) -> Tuple[str, str, Dict[str, int]]:
    """
    Mécanisme RG-00 :
    - interroge chaque scénario,
    - récupère un score 0-100,
    - choisit le meilleur si score >= MIN_SCORE,
    - sinon renvoie KO_SCENARIO + famille générique.

    Retourne (scenario_id, family, scores_par_scenario).
    """

    best_id = "KO_SCENARIO"
    best_family = "GENERIC_EF_Q1"
    best_score = 0
    scores: Dict[str, int] = {}

    for rule in SCENARIO_RULES:
        scen_id = rule["id"]
        family = rule["family"]
        score_fn: Callable[[Any], int] = rule["score_fn"]

        try:
            score = int(score_fn(ctx) or 0)
        except Exception as e:
            logger.exception("[RG-00] Erreur dans le score_fn pour %s : %s", scen_id, e)
            score = 0

        scores[scen_id] = score

        if score > best_score:
            best_score = score
            best_id = scen_id
            best_family = family

    if best_score < MIN_SCORE:
        logger.info("[RG-00] Aucun scénario >= %s, KO_SCENARIO", MIN_SCORE)
        return "KO_SCENARIO", "GENERIC_EF_Q1", scores

    logger.info(
        "[RG-00] Scénario retenu : %s (famille=%s, score=%s)",
        best_id, best_family, best_score
    )
    return best_id, best_family, scores

def select_model_family(context):
    """
    Sélectionne le model_family en fonction du scénario.
    Pour SC-001, on retourne MARA_REPRISE_Q1.
    """

    # Detect SC-001 (Marathon 3h45 Reprise)
    if (
        getattr(context, "mode", None) == "running"
        and getattr(context, "submode", None) == "reprise"
        and getattr(context, "objective_type", None) == "marathon"
        and getattr(context, "objective_time", None) in ("3:45", "3:45:00")
        and (getattr(context, "age", None) is None or 40 <= context.age <= 55)
    ):
        return "MARA_REPRISE_Q1"

    # fallback générique
    return "GENERIC_EF_Q1"
