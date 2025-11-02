# qualite/controle_rg.py

def to_number(value):
    """Convertit proprement les valeurs Airtable (num, str, list)."""
    if isinstance(value, list) and len(value) > 0:
        value = value[0]
    try:
        return float(value)
    except:
        return None


def verifier_vdot(record):
    """
    Vérifie la cohérence du VDOT.
    Retourne un tuple (etat, message, vdot_utilise_final).
    """

    vdot_initial = to_number(record.get("VDOT_initial"))
    vdot_moyen = to_number(record.get("VDOT_moyen_LK"))
    vdot_utilise = to_number(record.get("VDOT_utilisé"))

    # 1) Cas où aucune donnée VDOT n’est exploitable → bloquant
    if not vdot_initial and not vdot_moyen and not vdot_utilise:
        return ("KO", "⛔ Aucun VDOT disponible (ni chrono ni estimation).", None)

    # 2) Cas courant : retour / reprise → pas de chrono, mais VDOT_utilisé existe
    if not vdot_initial and vdot_utilise:
        return ("OK", f"✅ VDOT estimé utilisé ({vdot_utilise}).", vdot_utilise)

    # 3) Cas normal : VDOT basé sur données de référence
    if vdot_initial:
        return ("OK", f"✅ VDOT basé sur référence ({vdot_initial}).", vdot_initial)

    # 4) Cas fallback : on prend le meilleur dispo
    if vdot_moyen:
        return ("OK", f"✅ VDOT moyen historique utilisé ({vdot_moyen}).", vdot_moyen)

    return ("KO", "⛔ VDOT non déterminable.", None)
