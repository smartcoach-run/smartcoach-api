# ============================================================
#  data_provider_airtable.py
#  Provider officiel Airtable pour SCN_0g / SCN_6 / Step6
# ============================================================

import os
import requests
import logging

logger = logging.getLogger("smartcoach.data_provider")

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_DEV_BASE_ID")

TABLE_COU = os.getenv("AIRTABLE_COU_TABLE_DEV")        # 👟 Coureurs
TABLE_SLOTS = os.getenv("AIRTABLE_SLOTS_TABLE_DEV")    # 🧩 Slots
TABLE_TYPES = os.getenv("AIRTABLE_SEANCES_TYPES_DEV")  # 📘 Séances Types


# ============================================================
# Helper : airtable query
# ============================================================

def airtable_get(table_id, record_id=None, formula=None):
    url = f"https://api.airtable.com/v0/{BASE_ID}/{table_id}"

    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }

    if record_id:
        # Lecture d’un seul record
        r = requests.get(f"{url}/{record_id}", headers=headers)
        r.raise_for_status()
        return r.json()

    params = {}
    if formula:
        params["filterByFormula"] = formula

    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()


# ============================================================
# Charger un coureur
# ============================================================

def load_runner(record_id):
    """
    Retourne :
    {
        "id": ...,
        "mode": ...,
        "niveau": ...,
        "objectif": ...,
        "vdot": ...
    }
    """

    res = airtable_get(TABLE_COU, record_id=record_id)

    f = res["fields"]

    runner = {
        "id": record_id,
        "mode": f.get("Mode"),
        "niveau": f.get("Niveau_normalisé"),
        "objectif": f.get("Objectif_normalisé"),
        "vdot": f.get("VDOT"),
    }

    logger.info(f"[Provider] Runner loaded: {runner}")
    return runner


# ============================================================
# Charger un slot
# ============================================================

def load_slot(slot_id):
    """
    Retourne :
    {
        "id": slot_id,
        "jour": ...,
        "date": ...,
        "semaine": ...,
        "phase": ...,
        "categorie": Type_cible,
        "plan_id": ...
    }
    """

    formula = f"{{Slot_ID}} = '{slot_id}'"
    res = airtable_get(TABLE_SLOTS, formula=formula)

    if not res.get("records"):
        raise ValueError(f"Slot introuvable : {slot_id}")

    rec = res["records"][0]["fields"]

    slot = {
        "id": slot_id,
        "jour": rec.get("Jour_nom"),
        "date": rec.get("Date_slot"),
        "semaine": rec.get("Semaine_num"),
        "phase": rec.get("Phase"),
        "categorie": rec.get("Type_cible"),   # = Catégorie_moteur
        "plan_id": rec.get("Plan_ID"),
    }

    logger.info(f"[Provider] Slot loaded: {slot}")
    return slot


# ============================================================
# Charger les modèles de séances (Séances Types)
# ============================================================

def load_seances_types(filters):
    """
    Filters = {
        "Mode": ...,
        "Catégorie_moteur": ...,
        "Phase cible": ...,
        "Objectif": ...,
        "Niveau": ...
    }
    """

    # Construction dynamique du filterByFormula
    clauses = []
    for k, v in filters.items():
        if v is not None:
            clauses.append(f"{{{k}}} = '{v}'")

    formula = "AND(" + ",".join(clauses) + ")"

    res = airtable_get(TABLE_TYPES, formula=formula)
    return res.get("records", [])


# ============================================================
# Select best match + fallbacks
# ============================================================

def select_best_model(runner, slot):
    """
    Filtres successifs :
    1) Mode + Catégorie_moteur + Phase + Objectif + Niveau
    2) Relax Niveau
    3) Relax Objectif
    4) Relax Phase
    5) Safe Mode EF 25'
    """

    base_filters = {
        "Mode": runner["mode"],
        "Catégorie_moteur": slot["categorie"],
        "Phase cible": slot["phase"],
        "Objectif": runner["objectif"],
        "Niveau": runner["niveau"],
    }

    # 1) Filtre strict
    records = load_seances_types(base_filters)
    if records:
        return records[0]["fields"]

    # 2) Relax Niveau
    f2 = base_filters.copy()
    del f2["Niveau"]
    records = load_seances_types(f2)
    if records:
        return records[0]["fields"]

    # 3) Relax Objectif
    f3 = f2.copy()
    del f3["Objectif"]
    records = load_seances_types(f3)
    if records:
        return records[0]["fields"]

    # 4) Relax Phase
    f4 = f3.copy()
    del f4["Phase cible"]
    records = load_seances_types(f4)
    if records:
        return records[0]["fields"]

    # 5) SAFE MODE
    return {
        "Catégorie_moteur": "EF",
        "Clé séance": "SAFE_EF_25",
        "Durée (min)": 25,
        "Description": "Sortie en endurance fondamentale, 25 minutes faciles.",
    }


# ============================================================
# Adapter le modèle selon le coureur / VDOT / phase
# ============================================================

def adapt_model_to_runner(model, runner, slot):
    """
    Retourne une séance finale SCN_0g-friendly.
    """

    duree = model.get("Durée (min)", 30)

    # Ajustement simple V1
    vdot = runner.get("vdot")
    if vdot:
        # Exemple simple :
        if vdot > model.get("VDOT_max", 999):
            duree = int(duree * 1.05)
        elif vdot < model.get("VDOT_min", 0):
            duree = int(duree * 0.9)

    # Ajustement selon la phase
    phase = slot["phase"]
    if phase == "Peak":
        duree = int(duree * 1.1)
    elif phase == "Affûtage":
        duree = int(duree * 0.85)

    final = {
        "slot_id": slot["id"],
        "categorie": slot["categorie"],
        "nom": model.get("Clé séance"),
        "description": model.get("Description"),
        "duree_min": duree,
        "phase": slot["phase"],
        "semaine": slot["semaine"],
        "jour": slot["jour"],
    }

    logger.info(f"[Provider] Final model adapted: {final}")
    return final
