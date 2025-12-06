# ===============================================================
# Helpers pour SCN_0a et SCN_0c
# Normalisation des champs, parsing chrono, estimation du VDOT
# ===============================================================

import datetime
from typing import List, Optional

# ---------------------------------------------------------------
# Normalisation du mode
# ---------------------------------------------------------------
def normalize_mode(raw: str) -> Optional[str]:
    """
    Retourne un code stable parmi : RUN, VTL, KIDS, HYROX.
    """
    if not raw:
        return None

    raw = raw.strip().lower()

    if raw in ["running", "run"]:
        return "RUN"
    if raw in ["vitalite", "vitalité", "vtl"]:
        return "VTL"
    if raw in ["kids", "kid"]:
        return "KIDS"
    if raw in ["hyrox", "trx", "hy"]:
        return "HYROX"

    return None


# ---------------------------------------------------------------
# Normalisation des jours disponibles
# ---------------------------------------------------------------
def normalize_jours(raw) -> List[str]:
    """
    Nettoie la liste des jours sélectionnés dans Airtable.
    Exemple raw = ["Lundi", "Mardi"] → ["Lundi", "Mardi"]
    """
    if not raw:
        return []

    if isinstance(raw, list):
        return [str(j).strip() for j in raw]

    return [str(raw).strip()]


# ---------------------------------------------------------------
# Normalisation de la date objectif
# ---------------------------------------------------------------
def normalize_date(raw) -> Optional[datetime.date]:
    """
    Convertit une date type Airtable (string "2025-10-30") en date Python.
    """
    if not raw:
        return None

    try:
        return datetime.date.fromisoformat(str(raw))
    except Exception:
        return None


# ---------------------------------------------------------------
# Parsing d’un chrono "HH:MM:SS" ou "MM:SS"
# ---------------------------------------------------------------
def _parse_time(text: str) -> int:
    """
    Convertit un chrono string en nombre de secondes.
    Ex : "45:30" -> 2730 sec.
    Ex : "1:02:30" -> 3750 sec.
    """
    if not text:
        return None

    parts = text.split(":")

    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + int(seconds)

    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)

    return None


# ---------------------------------------------------------------
# Estimation VDOT : version simple (placeholder)
# ---------------------------------------------------------------
def estimate_vdot(objectif: str, chrono_seconds: int) -> Optional[float]:
    """
    Fonction placeholder simple.
    Plus tard, cette fonction sera remplacée par ton vrai algo VDOT.
    """
    if not objectif or not chrono_seconds:
        return None

    # Ici une formule très simple juste pour débloquer la pipeline :
    # → moins le chrono est long, plus le VDOT est élevé
    base_ref = {
        "5K": 1500,
        "10K": 3200,
        "HM": 7200,
        "M": 15000
    }

    objectif_norm = objectif.upper()
    ref = base_ref.get(objectif_norm)

    if not ref:
        return None

    # Formule simplifiée (à remplacer plus tard : Daniels)
    vdot = max(20, min(70, ref / (chrono_seconds / 10)))

    return round(vdot, 1)
