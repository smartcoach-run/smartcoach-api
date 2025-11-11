from airtable import airtable_get_one

def lookup_reference_jours(cf):
    key = f"{cf.get('Mode')}-{cf.get('Niveau')}-{cf.get('Objectif')}"
    row = airtable_get_one("Référence Jours", "Clé_niveau_reference", key)
    if not row:
        return None
    fields = row["fields"]
    return {
        "Nb_jours_min": fields.get("Nb_jours_min", 0),
        "Nb_jours_max": fields.get("Nb_jours_max", 0),
        "Jours_proposés": fields.get("Jours_proposés", []),
    }
