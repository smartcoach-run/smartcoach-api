def verifier_vdot(fields):

    vdot_utilise = fields.get("VDOT_utilisé")
    vdot_initial = fields.get("VDOT_initial")
    vdot_moyen = fields.get("VDOT_moyen_LK")

    print("📥 DEBUG VDOT")
    print("  → VDOT_utilisé :", vdot_utilise)
    print("  → VDOT_initial :", vdot_initial)
    print("  → VDOT_moyen_LK :", vdot_moyen)

    # RG B04-VDOT-02 : Pas de chrono → on prend le niveau → message coach motivant
    if vdot_utilise is None:
        return "OK", "SC_COACH_003", vdot_initial or vdot_moyen

    # Si valeur incohérente (rare mais on garde)
    if isinstance(vdot_utilise, (int, float)) and vdot_utilise < 10:
        return "KO", "SC_WARN_001", vdot_utilise

    return "OK", "SC_COACH_003", vdot_utilise
