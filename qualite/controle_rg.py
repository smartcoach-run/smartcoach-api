def verifier_vdot(fields):
    """
    Vérifie la valeur de VDOT à utiliser en fonction des règles de gestion.
    Règle principale : B04-VDOT-02

    Champs utilisés :
      - VDOT_utilisé : valeur finale normalement calculée ou saisie
      - VDOT_initial : valeur par défaut issue du niveau du coureur
      - VDOT_moyen_LK : estimation issue d'une éventuelle course de référence

    Logique :
      1) Si aucune valeur "VDOT_utilisé" → on applique la logique par niveau (SC_COACH_003)
      2) Si une valeur existe mais aberrante (<10) → alerte qualité (SC_WARN_001)
      3) Sinon → on valide (SC_COACH_003)
    """

    # Normalisation du nom de champ
    # (permet d'accepter "VDOT utilisé" ou "VDOT_utilisé")
    vdot_utilise = fields.get("VDOT_utilisé") or fields.get("VDOT utilisé")

    vdot_initial = fields.get("VDOT_initial")
    vdot_moyen = fields.get("VDOT_moyen_LK")

    # Logs lisibles dans Render
    print("📥 DEBUG VDOT")
    print("  → VDOT_utilisé :", vdot_utilise)
    print("  → VDOT_initial :", vdot_initial)
    print("  → VDOT_moyen_LK :", vdot_moyen)

    # --- RG B04-VDOT-02 ---
    # Cas standard du scénario 1 :
    # → Pas de chrono → pas de VDOT issu d’effort réel → on utilise le VDOT du niveau
    if vdot_utilise is None:
        vdot_calcule = vdot_initial or vdot_moyen
        return "OK", "SC_COACH_003", vdot_calcule

    # --- Cohérence qualité ---
    # Rare, mais si quelqu’un met une valeur absurde (<10 → marche lente)
    if isinstance(vdot_utilise, (int, float)) and vdot_utilise < 10:
        return "KO", "SC_WARN_001", vdot_utilise

    # --- Cas normal ---
    # Le coureur a déjà un VDOT pertinent → on le garde
    return "OK", "SC_COACH_003", vdot_utilise


def verifier_jours(fields):
    """
    Vérifie et ajuste le nombre de jours d'entraînement selon les RG B03-COH.
    Champs utilisés :
      - 📅 Jours_disponibles
      - Nb_jours_min
      - Nb_jours_max
    
    Sortie :
      - etat ("OK")
      - message_id ("SC_COACH_001" ou "SC_COACH_002")
      - jours_final (int)
    """

    jours_dispo = fields.get("📅 Jours_disponibles")
    min_j = fields.get("Nb_jours_min")
    max_j = fields.get("Nb_jours_max")

    # Si pas de référentiel → on ne bloque jamais → on renvoie ce qui est disponible
    if min_j is None or max_j is None:
        # Par défaut, on valide
        return "OK", "SC_COACH_001", jours_dispo

    # --- RG B03-COH-06 : Aucun jour saisi
    if jours_dispo is None:
        jours_final = min_j
        return "OK", "SC_COACH_002", jours_final

    # --- RG B03-COH-04 : Jours < min
    if jours_dispo < min_j:
        jours_final = min_j
        return "OK", "SC_COACH_002", jours_final

    # --- RG B03-COH-05 : Jours > max
    if jours_dispo > max_j:
        jours_final = max_j
        return "OK", "SC_COACH_002", jours_final

    # --- B03-COH-01 & B03-COH-03 : Cohérent → on valide
    return "OK", "SC_COACH_001", jours_dispo
