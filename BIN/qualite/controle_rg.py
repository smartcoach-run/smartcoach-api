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
    Vérifie et ajuste le nombre de jours d'entraînement
    sur la base du référentiel Jours_min / Jours_max
    issu de 📘 Référentiel Niveaux.
    """

    jours_dispo = fields.get("📅Nb_jours_dispo")
    if jours_dispo is None:
        return "OK", None, 1  # fallback minimal => jamais bloquant

    ref = fields.get("📘 Référentiel Niveaux", [])
    if not isinstance(ref, list) or len(ref) == 0:
        return "OK", None, jours_dispo  # pas de référence => on garde

    # Airtable renvoie une liste d'IDs => ici on suppose que le script les a déjà enrichis
    # donc les valeurs min / max doivent être directement dans fields :
    jours_min = fields.get("Jours_min")
    jours_max = fields.get("Jours_max")

    # Si pas trouvés, on laisse sans correction
    if jours_min is None or jours_max is None:
        return "OK", None, jours_dispo

    try:
        jours_min = int(jours_min)
        jours_max = int(jours_max)
        jours_dispo = int(jours_dispo)
    except:
        return "OK", None, 1

    # RG B03-COH-01 — Trop bas → on remonte au min
    if jours_dispo < jours_min:
        return "WARN", "SC_COACH_003", jours_min

    # RG B03-COH-02 — Trop haut → on limite
    if jours_dispo > jours_max:
        return "WARN", "SC_COACH_004", jours_max

    # RG B03-COH-03 — Cohérent → pas de changement
    return "OK", "SC_COACH_002", jours_dispo
