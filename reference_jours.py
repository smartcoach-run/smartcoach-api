import os
from airtable import airtable_get_all

TABLE_REF_JOURS = os.environ.get("TABLE_VDOT_REF", "⚖️ Référence Jours")

def lookup_reference_jours(cf):
    mode = fget(cf, F_MODE)
    niveau = fget(cf, F_NIVEAU)
    objectif = fget(cf, F_OBJECTIF)

    # correspondance côté Référence Jours : Mode / Niveau / Objectif
    formula = f"AND({{Mode}}='{mode}', {{Niveau}}='{niveau}', {{Objectif}}='{objectif}')"
    records = TAB_REFJ.all(formula=formula)
    if not records:
        print(f"[DEBUG] lookup_reference_jours → aucun résultat pour {formula}")
    return records[0] if records else None
