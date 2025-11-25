# scenarios/selectors.py
# ============================================================
# Sélecteurs communs aux scénarios SmartCoach :
#  - normalisation des jours
#  - construction Step3 Running (jours retenus + phases)
# ============================================================

from typing import List, Dict, Any
from services.airtable_fields import ATFIELDS
from core.utils.logger import log_info

# Ordre canonique pour toute la logique Running
DAYS_ORDER = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


# ------------------------------------------------------------
# Normalisation : transforme [" dimanche ", "mardi"] → ["Dimanche", "Mardi"]
# ------------------------------------------------------------
def _normalize_days_list(raw_days: Any) -> List[str]:
    if not raw_days:
        return []

    normalized = []
    for d in raw_days:
        if not isinstance(d, str):
            continue
        d_clean = d.strip().capitalize()
        for ref in DAYS_ORDER:
            if d_clean.lower() == ref.lower():
                normalized.append(ref)
                break
    return normalized


# ------------------------------------------------------------
# Mapping des phases par objectif (version simplifiée)
# ------------------------------------------------------------
def _compute_phases_for_objectif(obj: str) -> List[Dict[str, Any]]:
    """
    Retourne une liste de phases standardisées.
    """
    phases_default = [
        {"id": 1, "nom": "Base", "semaines": 3},
        {"id": 2, "nom": "Construction", "semaines": 3},
        {"id": 3, "nom": "Affûtage", "semaines": 1},
    ]

    return phases_default


# ------------------------------------------------------------
# STEP 3 : Sélection des jours Running
# ------------------------------------------------------------
def build_step3_running(record: Dict[str, Any], step2_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Étape 3 – Sélection des jours & phases pour le mode Running.
    """

    fields = record.get("fields", {})

    # Jours utilisateur bruts
    jours_user_raw = fields.get(ATFIELDS.COU_JOURS_DISPO)
    user_days = _normalize_days_list(jours_user_raw)

    # Jours final visés
    jours_final = step2_data.get("jours_final") or step2_data.get("jours_user") or len(user_days)

    # Jours proposés
    jours_proposes_raw = step2_data.get("jours_proposes") or []
    proposed_days = _normalize_days_list(jours_proposes_raw)

    # 1) Base : jours utilisateur dans l’ordre
    chosen: List[str] = []
    for d in DAYS_ORDER:
        if d in user_days:
            chosen.append(d)

    # 2) Ajout si besoin
    if len(chosen) < jours_final:
        missing = jours_final - len(chosen)
        for d in DAYS_ORDER:
            if d in proposed_days and d not in chosen:
                chosen.append(d)
                missing -= 1
                if missing == 0:
                    break

    # 3) Fallback (rare)
    if len(chosen) < jours_final:
        for d in user_days + proposed_days:
            if len(chosen) >= jours_final:
                break
            if d not in chosen:
                chosen.append(d)

    # 4) Trop de jours → on tronque
    if len(chosen) > jours_final:
        ordered = [d for d in DAYS_ORDER if d in chosen]
        chosen = ordered[:jours_final]

    days_added = [d for d in chosen if d not in user_days]

    # Phases selon l’objectif
    phases = _compute_phases_for_objectif(step2_data.get("objectif"))

    log_info(
        f"SCN_1/Step3 → user_days={user_days}, chosen={chosen}, days_added={days_added}",
        module="SCN_1",
    )

    return {
        "status": "ok",
        "jours_retenus": chosen,
        "jours_final": jours_final,
        "plan_distance": step2_data.get("objectif"),
        "plan_nb_semaines": phases[0]["semaines"],  # temp
        "phases": phases,
    }
