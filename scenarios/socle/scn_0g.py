# scenarios/scn_0g.py
# SCN_0g — Génération d’une séance OnDemand (SOCLE v2025-12 complet, env-aware)

import logging
import os
import requests
import traceback

from core.utils.logger import log_info, log_error
from core.internal_result import InternalResult

from core.utils.logger import root_logger as logger
from core.internal_result import InternalResult

from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

#logger = logging.getLogger("SCN_0g")

# ==========================================================
#  Sélection d'environnement (DEV / PROD)
# ==========================================================

ENV_MODE = os.getenv("ENV_MODE", "dev").lower()  # "dev" ou "prod"

def _select_env_var(base_name: str) -> str | None:
    """
    Retourne la bonne variable en fonction de ENV_MODE.
    Exemple : base_name="AIRTABLE_BASE_ID" →
      - ENV_MODE=dev  → AIRTABLE_BASE_ID_DEV
      - ENV_MODE=prod → AIRTABLE_BASE_ID_PROD
    """
    suffix = "_DEV" if ENV_MODE == "dev" else "_PROD"
    full_name = f"{base_name}{suffix}"
    return os.getenv(full_name)


# ==========================================================
#  Configuration Airtable (normalisée)
# ==========================================================

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = _select_env_var("AIRTABLE_BASE_ID")

TABLE_COU = _select_env_var("AIRTABLE_COU_TABLE")          # 👟 Coureurs
TABLE_SLOTS = _select_env_var("AIRTABLE_SLOTS_TABLE")      # 🧩 Slots
TABLE_TYPES = _select_env_var("AIRTABLE_SEANCES_TYPES")    # 📘 Séances types


# ==========================================================
#  Helpers Airtable
# ==========================================================

def _airtable_get(table_id: str, record_id: str | None = None, formula: str | None = None):
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID or not table_id:
        raise RuntimeError("Configuration Airtable manquante pour SCN_0g")

    base_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"

    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    }

    if record_id:
        resp = requests.get(f"{base_url}/{record_id}", headers=headers)
        resp.raise_for_status()
        return resp.json()

    params = {}
    if formula:
        params["filterByFormula"] = formula

    resp = requests.get(base_url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()


# ==========================================================
#  Entrée principale SCN_0g
# ==========================================================
# scenarios/agregateur/scn_0g.py

def run_scn_0g(context):
    logger.info("[SCN_0g] Début SCN_0g")

    # ----------------------------------------------------
    # 1) Dispatch — sélection du modèle via SCN_6
    # ----------------------------------------------------
    model_family = getattr(context, "model_family", None)

    if model_family == "MARA_REPRISE_Q1":
        logger.info("[SCN_0g] Modèle MARA_REPRISE_Q1 détecté")
        built = build_mara_reprise_q1(context)

        return InternalResult.ok(
            data={
                "session": built["session"],
                "war_room": built.get("war_room", {}),
                "phase_context": {}
            },
            source="SCN_0g",
            message="Séance générée via modèle MARA_REPRISE_Q1"
        )

    # ----------------------------------------------------
    # Aucun modèle correspondant → erreur contrôlée
    # ----------------------------------------------------
    return InternalResult.error(
        message=f"Aucun model_family reconnu : {model_family}",
        source="SCN_0g"
    )

# ==========================================================
# SAFE MODE (RG-09)
# ==========================================================

def _safe_mode(session_info: dict) -> InternalResult:
    """
    EF 25' universelle.
    """
    return InternalResult.ok(
        message="SCN_0g → Safe Mode activé",
        source="SCN_0g",
        data={
            "slot_id": session_info["slot_id"],
            "type": "EF",
            "duree": 25,
            "distance": 3.5,
            "intensite": "basse",
            "phase": session_info["phase"],
            "semaine": session_info["semaine"],
            "jour": session_info["jour"],
            "date": session_info.get("date"),  # 👈 AJOUT
            "description": "Endurance fondamentale douce, aisée, relâchée.",
            "conseils": "Respire, reste facile, relâche tes épaules.",
            "vdot_used": session_info["vdot"],
            "mode": session_info["mode"],
            "modele_cle": "SAFE_EF_25",
        },
    )


# ==========================================================
#  DRIVERS SOCLE — Airtable
# ==========================================================

def _load_runner(record_id: str) -> dict:
    """
    Charge le coureur depuis 👟 Coureurs.
    Champs utilisés :
      - Mode
      - Niveau_normalisé
      - Objectif_normalisé
      - VDOT
    """
    res = _airtable_get(TABLE_COU, record_id=record_id)
    fields = res.get("fields", {})

    runner = {
        "id": record_id,
        "mode": fields.get("Mode"),
        "niveau": fields.get("Niveau_normalisé"),
        "objectif": fields.get("Objectif_normalisé"),
        "vdot": fields.get("VDOT"),
    }

    log_info(f"[SCN_0g] Runner chargé : {runner}")
    return runner


def _load_slot(slot_id: str) -> dict:
    """
    Charge un slot depuis 🧩 Slots à partir de Slot_ID.
    Champs utilisés :
      - Slot_ID
      - Jour_nom
      - Date_slot
      - Semaine_num
      - Phase
      - Type_cible (Catégorie_moteur côté moteur)
    """
    formula = f"{{Slot_ID}} = '{slot_id}'"
    res = _airtable_get(TABLE_SLOTS, formula=formula)
    records = res.get("records", [])

    if not records:
        raise ValueError(f"Slot introuvable dans Airtable : {slot_id}")

    f = records[0]["fields"]

    slot = {
        "id": slot_id,
        "jour": f.get("Jour_nom"),
        "date": f.get("Date_slot"),
        "semaine": f.get("Semaine_num"),
        "phase": f.get("Phase"),
        "categorie": f.get("Type_cible"),  # = Catégorie_moteur
        "plan_id": f.get("Plan_ID"),
    }

    log_info(f"[SCN_0g] Slot chargé : {slot}")
    return slot


def _load_seances_types(filters: dict) -> list[dict]:
    """
    Charge les séances types depuis 📘 Séances types
    avec un filterByFormula dynamique.
    Filters peut contenir :
      - Mode
      - Catégorie_moteur
      - Phase cible
      - Objectif
      - Niveau
    """
    clauses = []
    for key, value in filters.items():
        if value is not None:
            clauses.append(f"{{{key}}} = '{value}'")

    if not clauses:
        formula = None
    else:
        formula = "AND(" + ",".join(clauses) + ")"

    res = _airtable_get(TABLE_TYPES, formula=formula)
    records = res.get("records", [])
    return [r.get("fields", {}) for r in records]


def _find_model(runner: dict, slot: dict) -> dict | None:
    """
    Trouve le meilleur modèle en appliquant des filtres successifs :
      1) Mode + Catégorie_moteur + Phase + Objectif + Niveau
      2) Relax Niveau
      3) Relax Objectif
      4) Relax Phase
      5) Safe mode (None, géré en amont)
    """

    base_filters = {
        "Mode": runner.get("mode"),
        "Catégorie_moteur": slot.get("categorie"),
        "Phase cible": slot.get("phase"),
        "Objectif": runner.get("objectif"),
        "Niveau": runner.get("niveau"),
    }

    # 1) Filtre strict
    records = _load_seances_types(base_filters)
    if records:
        log_info("[SCN_0g] Modèle trouvé (filtre strict)")
        return records[0]

    # 2) Relax Niveau
    f2 = base_filters.copy()
    f2.pop("Niveau", None)
    records = _load_seances_types(f2)
    if records:
        log_info("[SCN_0g] Modèle trouvé (sans Niveau)")
        return records[0]

    # 3) Relax Objectif
    f3 = f2.copy()
    f3.pop("Objectif", None)
    records = _load_seances_types(f3)
    if records:
        log_info("[SCN_0g] Modèle trouvé (sans Objectif)")
        return records[0]

    # 4) Relax Phase
    f4 = f3.copy()
    f4.pop("Phase cible", None)
    records = _load_seances_types(f4)
    if records:
        log_info("[SCN_0g] Modèle trouvé (sans Phase)")
        return records[0]

    # 5) Aucun modèle
    log_info("[SCN_0g] Aucun modèle de séance trouvé (tous filtres)")
    return None


def _adapt_model(model: dict, runner: dict, slot: dict, feedback: dict | None = None) -> dict:
    """
    Adapte le modèle aux caractéristiques du coureur (VDOT, phase…)
    Retourne un dict :
      - duree_min
      - description
      - distance_km (optionnel)
      - intensite (optionnel)
      - conseils (optionnel)
      - modele_cle
    """
    if feedback:
        log_info("[SCN_0g] Feedback reçu mais non traité (placeholder v2)")  # ✅ PATCH 2

    adapted = model.copy()
    duree = model.get("Durée (min)", 30)
    try:
        duree = int(duree)
    except Exception:
        duree = 30

    vdot = runner.get("vdot")
    vdot_min = model.get("VDOT_min")
    vdot_max = model.get("VDOT_max")

    # Ajustement simple selon VDOT (si bornes renseignées)
    if isinstance(vdot, (int, float)):
        if vdot_max and vdot > vdot_max:
            duree = int(duree * 1.05)
        elif vdot_min and vdot < vdot_min:
            duree = int(duree * 0.9)

    # Ajustement selon la phase
    phase = slot.get("phase")
    if phase == "Peak":
        duree = int(duree * 1.1)
    elif phase in ("Affûtage", "Affutage"):
        duree = int(duree * 0.85)

    # Distance approximative (EF ~ 9 km/h, sinon neutre)
    categorie = slot.get("categorie") or model.get("Catégorie_moteur")
    distance_km = None
    if categorie == "EF":
        distance_km = round(duree * 9 / 60, 1)

    # Intensité simple
    if categorie == "EF":
        intensite = "basse"
    elif categorie in ("SL",):
        intensite = "modérée"
    elif categorie in ("T", "I", "R"):
        intensite = "élevée"
    else:
        intensite = None

    description = model.get("Description") or "Séance structurée selon ton plan."
    conseils = model.get("Conseils") if "Conseils" in model else None

    _ = feedback  # réservé pour la v2

    return {
        "duree_min": duree,
        "distance_km": distance_km,
        "intensite": intensite,
        "description": description,
        "conseils": conseils,
        "modele_cle": model.get("Clé séance"),
    }

def build_mara_reprise_q1(ctx):
    slot = getattr(ctx, "slot", {}) or {}
    record_id = getattr(ctx, "record_id", None)

    steps = [
        {"type": "EF", "duration_min": 20, "zone": "E"},
        {"type": "BLOCK", "repeats": 3, "steps": [
            {"type": "QUALITY", "duration_min": 5, "zone": "T_LIGHT"},
            {"type": "RECOVER", "duration_min": 3, "zone": "E"}
        ]},
        {"type": "COOLDOWN", "duration_min": 10, "zone": "E"},
    ]

    duration = 20 + 3*(5+3) + 10   # = 54 minutes

    session = {
        "session_id": f"sess_{slot.get('slot_id')}",
        "slot_id": slot.get("slot_id"),
        "record_id": record_id,
        "date": slot.get("date"),
        "phase": slot.get("phase"),
        "type": slot.get("type"),
        "steps": steps,
        "duration_total": duration,
        "metadata": {
            "engine_version": "1.0",
            "socle_version": "SCN_0g",
            "family": "MARA_REPRISE_Q1"
        }
    }

    war_room = {
        "chosen_model": "MARA_REPRISE_Q1",
        "planned_duration": duration
    }

    return {
        "session": session,
        "war_room": war_room
    }