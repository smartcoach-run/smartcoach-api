def controle_qualite(data: dict) -> dict:
    log = {}
    plan_ok = True

    # RG1 – VDOT obligatoire
    if not data.get("VDOT_initial"):
        log["Check_vdot"] = "⛔ VDOT manquant"
        plan_ok = False
    else:
        log["Check_vdot"] = "✅ OK"

    # RG2 – Nb jours min selon niveau
    nb_jours_dispo = len(data.get("📅 Jours_final", []))
    niveau = data.get("Niveau_normalisé", "")
    if niveau == "Débutant" and nb_jours_dispo < 2:
        log["Check_jours"] = "⛔ Trop peu de jours pour un débutant"
        plan_ok = False
    else:
        log["Check_jours"] = "✅ OK"

    # RG3 – Cohérence date course vs date aujourd’hui
    # (exemple, tu peux adapter)
    # …

    return {
        "plan_ok": plan_ok,
        "log": log,
    }
def run_all_checks(fields):
    """
    Applique les règles de gestion à un enregistrement Airtable
    """
    prenom = fields.get("Prénom", "athlète")
    niveau = fields.get("Niveau_normalisé", "")
    nb_jours = fields.get("📅Nb_jours_final", 0)
    vdot = fields.get("VDOT_utilisé", None)
    objectif = fields.get("Objectif_format_LK", "")

    resultats = {}

    # --- Règles simples ---
    if vdot is None:
        resultats["check_vdot"] = "⛔ VDOT manquant"
    else:
        resultats["check_vdot"] = f"✅ VDOT = {vdot}"

    if niveau == "":
        resultats["check_niveau"] = "⛔ Niveau vide"
    else:
        resultats["check_niveau"] = f"✅ Niveau = {niveau}"

    if isinstance(nb_jours, int) and nb_jours < 2:
        resultats["check_jours"] = f"⛔ Trop peu de jours ({nb_jours})"
    else:
        resultats["check_jours"] = f"✅ Nb jours = {nb_jours}"

    # --- Message coach personnalisé ---
    message_coach = f"🔥 {prenom}, ton plan pour le {objectif} commence !"
    resultats["🧠 Message_coach"] = message_coach

    return resultats
