# reference_jours.py
from airtable import airtable_get_all
import os

# Lis le nom de table depuis l'env, avec fallback EXACT sur ta base
TABLE_REF_JOURS = os.environ.get("TABLE_VDOT_REF", "⚖️ Référence Jours")

def lookup_reference_jours(cf):
    mode = (cf.get("Mode") or "").strip()
    niveau = (cf.get("Niveau") or "").strip()
    objectif = (cf.get("Objectif") or "").strip() or "None"  # si vide, clé 'None'
    key = f"{mode}-{niveau}-{objectif}"

    rows = airtable_get_all(
        TABLE_REF_JOURS,
        formula=f"{{Clé_niveau_reference}} = '{key}'",
        max_records=1
    )
    if not rows:
        return None

    f = rows[0]["fields"]
    jours_proposes = f.get("Jours_proposés", [])
    if isinstance(jours_proposes, str):
        jours_proposes = [jours_proposes]

    return {
        "jours_min": int(f.get("Nb_jours_min", 0) or 0),
        "jours_max": int(f.get("Nb_jours_max", 7) or 7),
        "jours_proposés": jours_proposes
    }