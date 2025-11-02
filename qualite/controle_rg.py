def verifier_vdot(record):
    fields = record.get("fields", {})

    # Lecture des champs
    vdot_utilise = fields.get("VDOT_utilisé")
    f_vdot_ref = fields.get("f_VDOT_ref")
    vdot_initial = fields.get("VDOT_initial")
    vdot_moyen = fields.get("VDOT_moyen_LK")

    print("📥 DEBUG VDOT")
    print("  → VDOT_utilisé :", vdot_utilise)
    print("  → f_VDOT_ref :", f_vdot_ref)
    print("  → VDOT_initial :", vdot_initial)
    print("  → VDOT_moyen_LK :", vdot_moyen)

    # Cas 1 : valeur utilisée absente
    if vdot_utilise is None:
        return "KO", "⛔ VDOT utilisé manquant dans la fiche", None

    # Cas 2 : valeur incohérente (ex. : vdot utilisé = 0 ou aberrant)
    if isinstance(vdot_utilise, (int, float)) and vdot_utilise < 10:
        return "KO", "⛔ VDOT trop faible ou incorrect", vdot_utilise

    # Cas 3 : cohérence avec la référence
    if f_vdot_ref is None:
        return "KO", "⛔ VDOT de référence manquant", vdot_utilise

    # Ajoute ici tes autres règles si besoin
    return "OK", "✅ VDOT vérifié avec succès", vdot_utilise
