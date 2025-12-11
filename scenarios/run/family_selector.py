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
