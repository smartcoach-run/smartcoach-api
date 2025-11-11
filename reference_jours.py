import os
from airtable import airtable_get_all

TABLE_REF_JOURS = os.environ.get("TABLE_VDOT_REF", "⚖️ Référence Jours")

def lookup_reference_jours(cf, debug=False):
    mode = (cf.get("Mode") or "").strip()
    niveau = (cf.get("Niveau") or "").strip()
    objectif = (cf.get("Objectif") or "").strip()

    # === DEBUG TRACE SCN_001 ===
    if debug:
        print("=== DEBUG SCN_001 / Lookup Référence Jours ===")
        print("Mode :", repr(mode))
        print("Niveau :", repr(niveau))
        print("Objectif (brut) :", repr(objectif))

    # Normalisation (V1-compatible)
    objectif = objectif.replace(" ", "").replace("km","").replace("KM","")
    # Harmonisation des notations de course
    objectif = objectif.upper().replace("5K","5K").replace("10K","10K")

    key = f"{mode}-{niveau}-{objectif}"

    if debug:
        print("Objectif (normalisé) :", repr(objectif))
        print("Clé générée :", repr(key))

    rows = airtable_get_all(
        TABLE_REF_JOURS,
        formula=f"{{Clé_niveau_reference}} = '{key}'",
        max_records=1
    )

    if not rows:
        return None  # -> SC_COACH_024 côté main

    return rows[0]["fields"]
