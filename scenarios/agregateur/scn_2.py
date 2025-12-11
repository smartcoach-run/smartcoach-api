# scenarios/agregateur/scn_2.py
"""
SCN_2 – Génération de séance RUNNING (niveau C – architecture prête pour personnalisation)

Rôle :
- Recevoir un run_context + phase_context
- Calculer un volume cible (durée / distance) en fonction du profil, de l’objectif, de la phase
- Sélectionner un bloc de séance (block_id) en fonction du type de séance (EF, I, T, M, R)
- Générer une séance structurée :
    - title
    - description
    - steps
    - distance_km
    - load
    - intensity_tags
- Retourner un dictionnaire "session" prêt à être intégré dans BAB_ENGINE_MVP

Ce module est centré sur RUNNING mais extensible à d’autres univers plus tard.
"""

from typing import Dict, Any, List, Tuple

from core.internal_result import InternalResult
from core.utils.logger import log_info, log_error

MODULE_NAME = "SCN_2"

# -------------------------------------------------------------------
# Config “C” simplifiée – à affiner plus tard
# -------------------------------------------------------------------

# Volumes cibles (en minutes) par niveau & phase d’entraînement
VOLUME_TARGET_MIN = {
    "debutant": {
        "General": (30, 45),
        "Specifique": (35, 55),
        "Affutage": (25, 40),
    },
    "intermediaire": {
        "General": (40, 60),
        "Specifique": (45, 75),
        "Affutage": (35, 50),
    },
    "avance": {
        "General": (45, 70),
        "Specifique": (55, 90),
        "Affutage": (40, 60),
    },
}

# Allures cibles “placeholder” en min/km selon niveau (en attendant VDOT)
PACE_E_MIN_PER_KM = {
    "debutant": 7.0,       # 7:00/km
    "intermediaire": 6.0,  # 6:00/km
    "avance": 5.0,         # 5:00/km
}

# Coefficients de charge simple (à raffiner plus tard)
LOAD_COEFF = {
    "E": 1.0,
    "M": 1.1,
    "T": 1.3,
    "I": 1.5,
    "R": 1.7,
}


# -------------------------------------------------------------------
# Helpers internes
# -------------------------------------------------------------------

def _get_level(profile: Dict[str, Any]) -> str:
    """
    Normalise le niveau à 'debutant' / 'intermediaire' / 'avance'.
    """
    raw = (profile.get("niveau") or profile.get("level") or "").lower()

    if "deb" in raw or raw == "n1":
        return "debutant"
    if "inter" in raw or raw == "n2":
        return "intermediaire"
    if "av" in raw or raw == "n3":
        return "avance"

    # défaut raisonnable
    return "debutant"


def _get_phase_name(phase_context: Dict[str, Any], slot: Dict[str, Any]) -> str:
    """
    Récupère le nom de la phase (General / Specifique / Affutage).
    """
    phase = phase_context.get("phase") or slot.get("phase") or "General"
    phase = str(phase).lower()

    if "affut" in phase:
        return "Affutage"
    if "spec" in phase:
        return "Specifique"
    return "General"


def _compute_volume_target_minutes(
    level: str,
    phase_name: str,
    historique: List[Dict[str, Any]],
    run_context: Dict[str, Any],
) -> int:
    """
    Calcule un volume cible (en minutes) pour la séance.
    - basé sur niveau + phase
    - ajustable plus tard avec l'historique (charge, fatigue)
    """
    default_range = (40, 50)

    phase_ranges = VOLUME_TARGET_MIN.get(level) or {}
    vol_range = phase_ranges.get(phase_name, default_range)

    base_min, base_max = vol_range

    # Ajustement simple selon historique (placeholder)
    # Ex : si dernière semaine très chargée -> on réduit légèrement
    recent_load = run_context.get("recent_load") or 0
    if recent_load > 1.2:   # charge forte
        base_max = max(base_min, base_max - 10)
    elif recent_load < 0.8:  # charge légère
        base_min = base_min + 5

    target = int((base_min + base_max) / 2)
    return max(20, target)


def _estimate_distance_km(duration_min: int, level: str) -> float:
    """
    Estimation de la distance à partir de la durée et d'une allure E simplifiée.
    """
    pace = PACE_E_MIN_PER_KM.get(level, 6.0)  # min/km
    km = duration_min / pace
    return round(km, 1)


def _compute_load(duration_min: int, intensity: str) -> int:
    """
    Calcul de charge simple : durée * coeff_intensité.
    """
    coeff = LOAD_COEFF.get(intensity, 1.0)
    return int(round(duration_min * coeff))


def _select_block_id(
    seance_type: str,
    phase_name: str,
    level: str,
    volume_target_min: int,
) -> str:
    """
    Sélectionne un block_id en fonction du type de séance, de la phase, du niveau et du volume.
    Ici, on reste simple mais la structure est prête pour la future BF.
    """
    seance_type = seance_type.upper()

    # Exemple de nomenclature :
    # BF_RUN_<TYPE>_<PHASE>_<LEVEL>_<VOLUME_ZONE>
    if volume_target_min <= 40:
        vol_tag = "SHORT"
    elif volume_target_min <= 60:
        vol_tag = "MEDIUM"
    else:
        vol_tag = "LONG"

    block_id = f"BF_RUN_{seance_type}_{phase_name.upper()}_{level.upper()}_{vol_tag}"
    return block_id


def _build_steps_for_ef(volume_target_min: int) -> List[Dict[str, Any]]:
    """
    Construction d'une séance EF simple :
    - pas d'échauffement/spécifique pour le MVP
    - à raffiner plus tard (split, éducatifs, retour au calme)
    """
    return [
        {
            "label": "Endurance fondamentale",
            "type": "E",
            "duration_min": volume_target_min,
            "comment": "Allure confortable, respiration aisée.",
        }
    ]


def _build_steps_from_block(
    block_id: str,
    seance_type: str,
    volume_target_min: int,
    level: str,
    phase_name: str,
) -> Tuple[List[Dict[str, Any]], float, int, List[str]]:
    """
    À terme : mapping complet block_id -> structure de séance.
    Pour l'instant :
    - si EF => séance continue
    - autres types : placeholder simple
    """
    seance_type = seance_type.upper()
    intensity_tags = [seance_type]

    if seance_type == "E" or seance_type == "EF":
        steps = _build_steps_for_ef(volume_target_min)
        distance_km = _estimate_distance_km(volume_target_min, level)
        load = _compute_load(volume_target_min, "E")
        return steps, distance_km, load, ["E"]

    # Placeholder pour les autres types : une seule étape
    steps = [
        {
            "label": f"Séance {seance_type} (MVP)",
            "type": seance_type,
            "duration_min": volume_target_min,
            "comment": f"Séance {seance_type} simple – structure à enrichir.",
        }
    ]
    distance_km = _estimate_distance_km(volume_target_min, level)
    load = _compute_load(volume_target_min, seance_type)
    return steps, distance_km, load, intensity_tags


# -------------------------------------------------------------------
# Générateur principal de séance RUNNING
# -------------------------------------------------------------------

def generate_running_session(
    run_context: Dict[str, Any],
    phase_context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Génère une séance RUNNING complète à partir du run_context et du phase_context.
    C'est la brique centrale niveau C pour l'univers RUNNING.
    """

    profile = run_context.get("profile") or {}
    objectif = run_context.get("objectif") or {}
    slot = run_context.get("slot") or {}
    historique = run_context.get("historique") or []

    mode = run_context.get("mode") or "ondemand"
    seance_type = phase_context.get("seance_type") or phase_context.get("type_seance") or "EF"

    level = _get_level(profile)
    phase_name = _get_phase_name(phase_context, slot)

    log_info(
        f"[{MODULE_NAME}] Génération séance RUNNING – "
        f"mode={mode}, type={seance_type}, level={level}, phase={phase_name}",
        module=MODULE_NAME,
    )

    volume_target_min = _compute_volume_target_minutes(
        level=level,
        phase_name=phase_name,
        historique=historique,
        run_context=run_context,
    )

    block_id = _select_block_id(
        seance_type=seance_type,
        phase_name=phase_name,
        level=level,
        volume_target_min=volume_target_min,
    )

    steps, distance_km, load, intensity_tags = _build_steps_from_block(
        block_id=block_id,
        seance_type=seance_type,
        volume_target_min=volume_target_min,
        level=level,
        phase_name=phase_name,
    )

    title = f"Séance {seance_type.upper()}"
    description = f"Séance {seance_type.upper()} générée par SmartCoach (niveau {level}, phase {phase_name})."

    session = {
        "session_id": run_context.get("session_id") or None,
        "slot_id": slot.get("slot_id"),
        "plan_id": run_context.get("plan_id"),
        "user_id": run_context.get("user_id") or "unknown",
        "title": title,
        "description": description,
        "date": slot.get("date"),
        "phase": phase_name,
        "type": slot.get("type") or "Séance",
        "duration_min": volume_target_min,
        "distance_km": distance_km,
        "load": load,
        "intensity_tags": intensity_tags,
        "steps": steps,
        "block_id": block_id,
        "phase_context": phase_context,
    }

    return session


# -------------------------------------------------------------------
# Wrapper SCN_2 compatible SOCLE (InternalResult)
# -------------------------------------------------------------------

def run_scn_2(context) -> InternalResult:
    """
    Point d'entrée SCN_2 côté scénarios.

    context : objet SOCLE (DummyContext / InternalContext) avec au minimum :
        - context.payload["run_context"]
        - context.payload["phase_context"] (optionnel au début)
    """
    try:
        payload = getattr(context, "payload", {}) or {}
        run_context = payload.get("run_context") or payload
        phase_context = payload.get("phase_context") or {}

        session = generate_running_session(run_context, phase_context)

        return InternalResult.ok(
            message="SCN_2 – Séance RUNNING générée",
            source=MODULE_NAME,
            data={
                "session": session,
                "phase_context": phase_context,
            },
        )

    except Exception as e:
        log_error(f"[{MODULE_NAME}] Exception : {e}", module=MODULE_NAME)
        return InternalResult.error(
            message=f"Exception SCN_2 : {e}",
            source=MODULE_NAME,
            data={},
        )
