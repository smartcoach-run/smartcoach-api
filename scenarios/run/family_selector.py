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

def _score_sc_001(ctx):
    score = 0

    # 1. Discipline et type
    if getattr(ctx, "objectif_normalisé", None) == "RUN_M":
        score += 30

    # 2. Niveau / sous-mode
    if ctx.submode == "reprise":
        score += 30

    # 3. Age (fourchette 35–55)
    if ctx.age and 35 <= ctx.age <= 55:
        score += 20

    # 4. Chrono cible compatible 3h45 (format tolérant)
    time_raw = str(ctx.objective_time or "").replace(":", "")
    # exemples acceptés : "345", "0345", "34500", "034500"
    if "345" in time_raw:
        score += 20

    return score

def _score_sc_002(ctx):
    score = 0

    # 1. Running plaisir (clé pivot Airtable)
    if getattr(ctx, "objectif_normalisé", None) == "RUN_PLAISIR":
        score += 60   # suffisant pour passer le seuil

    # 2. Adulte / reprise (papa de 40 ans 😄)
    if ctx.age and ctx.age >= 35:
        score += 10

    return score


# ---------- Table des scénarios déclarés ----------

ScenarioRule = Dict[str, Any]

SCENARIO_RULES: List[ScenarioRule] = [
    {
        "id": "SC-001",
        "family": "MARA_REPRISE_Q1",
        "score_fn": _score_sc_001,
    },
       {
        "id": "SC-002",
        "family": "GENERIC_EF_Q1",
        "score_fn": _score_sc_002,
    }, 
    # Plus tard :
    # {
    #   "id": "SC-002",
    #   "family": "XXX",
    #   "score_fn": _score_sc_002,
    # },
]


# ---------- Sélection principale (RG-00) ----------

def scenario_and_family(ctx: Any) -> Tuple[str, str, Dict[str, int]]:
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
