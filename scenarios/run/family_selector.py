# scenarios/families/family_selector.py

def select_model_family(ctx) -> str:
    """
    Sélectionne la famille de modèles SOCLE à utiliser
    en fonction du contexte SmartCoach.
    
    Version v0 : ne gère que SC-001 (Reprise Marathon 3h45).
    La logique sera étendue progressivement via les SF_xx.
    """

    objective = getattr(ctx, "objective_type", None)
    phase = getattr(ctx, "phase", None)
    submode = getattr(ctx, "submode", None)
    level = getattr(ctx, "vdot", None) or getattr(ctx, "level", None)

    # ------------------------------------------------------------------
    # SC-001 : Marathon / Reprise / objectif 3h45
    # ------------------------------------------------------------------
    if (
        objective == "marathon"
        and submode == "reprise"
        and phase == "Reprise"
    ):
        # On ne fixe pas un modèle ultra-spécifique (3h45) pour éviter
        # la multiplication explosive des classes.
        # => On renvoie une famille générique MARA_REPRISE_Q1
        return "MARA_REPRISE_Q1"

    # ------------------------------------------------------------------
    # Défaut (fallback)
    # ------------------------------------------------------------------
    return "GENERIC_EF_Q1"
