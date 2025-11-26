# scenarios/selectors.py
# ============================================================
# Sélecteurs communs aux scénarios SmartCoach :
#  - normalisation des jours
#  - construction Step3 Running (jours retenus + phases)
#  - Step4 structure brute
#  - Step5 phases + progression
# ============================================================

from typing import List, Dict, Any
from services.airtable_fields import ATFIELDS
from core.utils.logger import log_info

# ------------------------------------------------------------
# Ordre canonique simple (utilisé en normalisation, Step3)
# ------------------------------------------------------------
DAYS_ORDER = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

# ------------------------------------------------------------
# Ordre naturel final (utilisé pour les tris Step4 et Step5)
# ------------------------------------------------------------
ORDER = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
ORDER_MAP = {day: i for i, day in enumerate(ORDER)}


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
# Mapping des phases par objectif (version simple)
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

    # Phases selon objectif
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
        "plan_nb_semaines": phases[0]["semaines"],  # temporaire
        "phases": phases,
    }


# ------------------------------------------------------------
# STEP 4 : Construction des semaines brutes Running
# ------------------------------------------------------------
def build_step4_running(
    distance: str,
    nb_semaines: int,
    jours_retenus: List[str]
) -> Dict[str, Any]:
    """
    STEP 4 — Génère la structure brute des semaines (sans phases).
    """

    # --- Correction : trier jours_retenus selon ordre naturel ---
    jours_retenus = sorted(jours_retenus, key=lambda d: ORDER_MAP.get(d, 99))
    log_info(f"STEP4 → ordre corrigé des jours : {jours_retenus}", module="SCN_1")

    # 1) Mapper les jours en ordre relatif
    jours_relatifs = {
        jour: i + 1
        for i, jour in enumerate(jours_retenus)
    }

    log_info(
        f"STEP4/Running → distance={distance}, nb_semaines={nb_semaines}, jours_retenus={jours_retenus}, jours_relatifs={jours_relatifs}",
        module="SCN_1",
    )

    # 2) Générer les semaines
    weeks = []
    for w in range(1, nb_semaines + 1):
        # slots triés selon ordre canonique
        slots = sorted(
            [
                {
                    "jour": j,
                    "jour_relatif": jours_relatifs[j],
                }
                for j in jours_retenus
            ],
            key=lambda s: ORDER_MAP.get(s["jour"], 99)
        )

        weeks.append({
            "semaine": w,
            "phase": None,
            "phase_distance": None,
            "phase_index": None,
            "slots": slots
        })

    return {
        "status": "ok",
        "plan_distance": distance,
        "plan_nb_semaines": nb_semaines,
        "jours_retenus": jours_retenus,
        "jours_relatifs": jours_relatifs,
        "weeks": weeks
    }


# ------------------------------------------------------------
# STEP 5 : Phases + progression
# ------------------------------------------------------------
def apply_phases_to_weeks(step4_weeks: List[Dict[str, Any]], phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    weeks_filled = []
    current_week = 1

    for phase in phases:
        phase_name = phase.get("nom")
        phase_weeks = phase.get("semaines", 0)
        phase_index = phase.get("id")
        distance = phase.get("distance") or phase.get("phase_distance") or None

        for i in range(phase_weeks):
            matching_week = next((w for w in step4_weeks if w["semaine"] == current_week), None)
            if not matching_week:
                continue

            weeks_filled.append({
                **matching_week,
                "phase": phase_name,
                "phase_index": phase_index,
                "phase_distance": distance
            })

            current_week += 1

    return weeks_filled


def apply_phases_and_progression(weeks: List[Dict[str, Any]], phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Step5 – Assigne les phases et calcule la courbe de charge progressive.
    """

    # 1) Expand phases
    expanded_phases = []
    for ph in phases:
        expanded_phases += [ph["nom"]] * ph["semaines"]

    total_weeks = len(weeks)
    if total_weeks == 0:
        return weeks

    # 2) Courbe de charge
    min_load = 0.30
    max_load = 0.85
    load_step = (max_load - min_load) / max(total_weeks - 1, 1)

    def compute_load(i: int) -> float:
        return round(min_load + i * load_step, 3)

    # 3) Génération enrichie
    enriched = []
    for i, w in enumerate(weeks):

        # --- Correction Step5 : tri naturel des slots ---
        w["slots"] = sorted(
            w.get("slots", []),
            key=lambda s: ORDER_MAP.get(s.get("jour"), 99)
        )

        phase_name = expanded_phases[i] if i < len(expanded_phases) else None
        phase_index = None

        # déterminer index de phase
        if phase_name:
            start = 0
            for ph in phases:
                if ph["nom"] == phase_name:
                    break
                start += ph["semaines"]
            phase_index = (i - start) + 1

        enriched.append({
            **w,
            "phase": phase_name,
            "phase_index": phase_index,
            "charge_pct": compute_load(i)
        })

    return enriched
