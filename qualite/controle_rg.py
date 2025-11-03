def verifier_vdot(fields):
    """
    Détermine le VDOT à utiliser selon les règles de gestion.
    Champs utilisés :
      - VDOT_utilisé (peut être vide)
      - VDOT_initial (valeur issue du niveau déclaré)
      - VDOT_moyen_LK (fallback si jamais initial absent)
      - 🔥 Ton expérience (pour détecter Reprise)

    Sortie :
      - etat ("OK" ou "KO")
      - message_id (clé pour lookup dans 🗂️ Messages SmartCoach)
      - vdot_final (float ou int)
    """

    experience = fields.get("🔥 Ton expérience")
    vdot_utilise = fields.get("VDOT_utilisé")
    vdot_initial = fields.get("VDOT_initial")
    vdot_moyen = fields.get("VDOT_moyen_LK")

    print("📥 DEBUG VDOT")
    print("  → Expérience :", experience)
    print("  → VDOT_utilisé :", vdot_utilise)
    print("  → VDOT_initial :", vdot_initial)
    print("  → VDOT_moyen :", vdot_moyen)

    # --- B04-VDOT-03 : Profil Reprise → Sécurisation démarrage
    if experience in ["Reprise", "Retour après coupure", "Débutant"]:
        vdot_final = vdot_initial or vdot_moyen
        return "OK", "SC_COACH_003", vdot_final

    # --- B04-VDOT-02 : Pas de chrono / pas de VDOT_utilisé → on prend VDOT_initial
    if vdot_utilise is None:
        vdot_final = vdot_initial or vdot_moyen
        return "OK", "SC_COACH_003", vdot_final

    # --- Cas rare : VDOT incohérent → on avertit
    if isinstance(vdot_utilise, (int, float)) and vdot_utilise < 10:
        return "KO", "SC_WARN_001", vdot_utilise

    # --- Cas normal : tout est cohérent
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
