# scenarios/builders.py
# =============================================================
# Fonctions de construction communes aux scénarios fonctionnels
# (SCN_1, SCN_0c, SCN_0d, ...)
# =============================================================

from typing import Any, Dict, List
import os

from pyairtable import Table

from services.airtable_fields import ATFIELDS, get_field
from services.airtable_tables import ATABLES
from core.utils.logger import log_info, log_warning


# -------------------------------------------------------------
# STEP 3 – MODE RUNNING
#  - Sélection des jours finaux
#  - Récupération de la configuration de phases (🛣️ Mapping Phase)
# -------------------------------------------------------------

def build_step3_running(record: Dict[str, Any], step2_data: Dict[str, Any]) -> Dict[str, Any]:
    """Construit le bloc Step3 pour le mode Running.

    Version corrigée :
    - les jours retenus proviennent directement de SCN_0b
      (jours_result.jours_valides = source de vérité),
    - on ne rebricole plus la liste à partir de REF_JOURS ici,
      pour éviter de contredire le SOCLE.
    """

    fields = record.get("fields", {}) or {}

    # 1) Jours utilisateur (pour info / logs)
    user_days_raw = get_field(record, ATFIELDS.COU_JOURS_DISPO, default=[])
    if user_days_raw is None:
        user_days_raw = []
    if not isinstance(user_days_raw, list):
        user_days_raw = [user_days_raw]

    # 2) Jours optimisés par SCN_0b
    jours_result = step2_data.get("jours_result", {}) or {}
    chosen_days: List[str] = jours_result.get("jours_valides", [])

    if not chosen_days:
        # Fallback de sécurité : on repart sur les jours saisis
        chosen_days = list(user_days_raw)

    # Jours ajoutés = jours présents dans chosen_days mais pas saisis par l'utilisateur
    days_added = [d for d in chosen_days if d not in user_days_raw]

    log_info(
        f"SCN_1/Step3 → user_days={user_days_raw}, "
        f"chosen={chosen_days}, days_added={days_added}",
        module="SCN_1",
    )

    # 🔧 Ordre canonique de la semaine (Lundi → Dimanche), indispensable pour SCN_0d.
    try:
        ordered = [
            j
            for j in [
                "Lundi", "Mardi", "Mercredi", "Jeudi",
                "Vendredi", "Samedi", "Dimanche",
            ]
            if j in chosen_days
        ]
        chosen_days = ordered
    except Exception:
        # Sécurité : on garde l'ordre existant en cas de problème
        pass

    # 3) Phases (🛣️ Mapping Phase)
    objectif = get_field(record, ATFIELDS.COU_OBJECTIF_NORMALISE)
    mode = get_field(record, ATFIELDS.COU_MODE)
    duree_plan_raw = get_field(record, ATFIELDS.COU_DUREE_PLAN_CALC)

    nb_semaines_plan = None
    if isinstance(duree_plan_raw, (int, float)):
        nb_semaines_plan = int(duree_plan_raw)
    else:
        try:
            nb_semaines_plan = int(duree_plan_raw) if duree_plan_raw is not None else None
        except (TypeError, ValueError):
            nb_semaines_plan = None

    phases: List[Dict[str, Any]] = []
    if (mode or "").lower() == "running" and objectif:
        phases = _load_mapping_phases(distance=objectif)

    step3_payload: Dict[str, Any] = {
        "status": "ok",
        # Jours
        "jours_user": user_days_raw,
        "jours_retenus": chosen_days,
        "jours_final": len(chosen_days),
        "jours_proposes": [],          # plus gérés ici (SOCLE = SCN_0b)
        "jours_ajoutes": days_added,
        "jours_result": jours_result,  # on garde la structure SOCLE si besoin
        # Phases
        "plan_distance": objectif,
        "plan_nb_semaines": nb_semaines_plan,
        "phases": phases,
    }

    return step3_payload

# -------------------------------------------------------------
# Helpers internes
# -------------------------------------------------------------

def _load_mapping_phases(distance: str) -> List[Dict[str, Any]]:
    """Récupère les phases dans la table 🛣️ Mapping Phase pour une distance donnée.

    On s'appuie uniquement sur les données Airtable, aucune valeur métier
    n'est codée en dur dans le code.
    """

    api_key = os.getenv("AIRTABLE_API_KEY")
    base_id = os.getenv("AIRTABLE_BASE_ID")

    if not api_key or not base_id:
        log_warning(
            "Mapping Phase → variables d'environnement Airtable manquantes (API KEY / BASE ID)",
            module="SCN_1",
        )
        return []

    try:
        table_name = ATABLES.MAPPING_PHASES  # ⚠️ à déclarer dans services/airtable_tables.py
    except AttributeError:
        log_warning(
            "ATABLES.MAPPING_PHASES non défini → aucune phase chargée.",
            module="SCN_1",
        )
        return []

    table = Table(api_key, base_id, table_name)

    # Filtre : uniquement les lignes correspondant à la distance (5K, 10K, HM, M…)
    formula = f"{{Distance}}='{distance}'"
    log_info(f"Mapping Phase → formula={formula}", module="SCN_1")

    try:
        records = table.all(formula=formula)
    except Exception as e:
        log_warning(
            f"Erreur lors de la lecture de la table Mapping Phase : {e}",
            module="SCN_1",
        )
        return []

    # Transformation en structure simple et ordonnée
    phases: List[Dict[str, Any]] = []
    for rec in records:
        f = rec.get("fields", {})

        distance_val = f.get(getattr(ATFIELDS, "MP_DISTANCE", "Distance"), distance)

        phase_dict: Dict[str, Any] = {
            "distance": distance_val,
            "phase_cle": f.get(getattr(ATFIELDS, "MP_PHASE_CLE", "Phase (clé)")),
            "ordre_phase": f.get(getattr(ATFIELDS, "MP_ORDRE_PHASE", "Ordre phase")),
            "semaine_debut": f.get(getattr(ATFIELDS, "MP_SEM_DEBUT", "Semaine début")),
            "semaine_fin": f.get(getattr(ATFIELDS, "MP_SEM_FIN", "Semaine fin")),
            "pct_debut": f.get(getattr(ATFIELDS, "MP_PCT_DEBUT", "Pct_debut")),
            "pct_fin": f.get(getattr(ATFIELDS, "MP_PCT_FIN", "Pct_fin")),
        }

        phases.append(phase_dict)

    # Tri sécurisé par ordre de phase
    phases.sort(key=lambda p: (p.get("ordre_phase") or 0))

    return phases

# =============================================================
# Builders génériques pour les scénarios fonctionnels SmartCoach
# - Step4 : squelette hebdomadaire (Running)
# =============================================================

from typing import Any, Dict, List

from core.utils.logger import log_info


JOURS_ORDONNES = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
]


def _compute_jours_relatifs(jours_retenus: List[str]) -> Dict[str, int]:
    """
    Convertit une liste de jours (ex. ['Mardi','Vendredi','Dimanche'])
    en index relatifs dans la semaine : 1,2,3...
    """
    mapping: Dict[str, int] = {}
    # On normalise en gardant l'ordre logique de la semaine
    ordered = [j for j in JOURS_ORDONNES if j in jours_retenus]
    for idx, jour in enumerate(ordered, start=1):
        mapping[jour] = idx
    return mapping


def _build_weeks_from_phases(
    plan_nb_semaines: int,
    phases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Construit la structure (semaine -> phase) à partir des phases calculées
    à l'étape 3.

    Chaque élément de `phases` est supposé avoir :
    - distance
    - phase_cle
    - ordre_phase
    - semaine_debut
    - semaine_fin
    """
    weeks: List[Dict[str, Any]] = []

    for semaine in range(1, plan_nb_semaines + 1):
        phase_label = None
        phase_distance = None
        phase_index = None

        for phase in phases:
            sd = phase.get("semaine_debut")
            sf = phase.get("semaine_fin")
            if sd is None or sf is None:
                continue
            if sd <= semaine <= sf:
                phase_label = phase.get("phase_cle")
                phase_distance = phase.get("distance")
                phase_index = phase.get("ordre_phase")
                break

        weeks.append(
            {
                "semaine": semaine,
                "phase": phase_label,
                "phase_distance": phase_distance,
                "phase_index": phase_index,
            }
        )

    return weeks


def build_step4_running(step3_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    STEP4 (version SOCLE) – Construction du squelette hebdomadaire.

    👉 Important :
    - Cette version ne sélectionne PAS encore les modèles de séances.
    - Elle construit un canevas propre :
        - semaines
        - phase associée
        - slots d'entraînement (jour + jour_relatif)
    - La sélection des séances types (catalogue) sera gérée
      dans un scénario technique (SCN_0c) ou une V2 de Step4.

    Entrée (step3_data attendu) :
    {
        "status": "ok",
        "jours_user": [...],
        "jours_retenus": [...],
        "jours_final": 3,
        "plan_distance": "10K",
        "plan_nb_semaines": 9,
        "phases": [...]
    }

    Sortie :
    {
        "status": "ok",
        "plan_distance": "10K",
        "plan_nb_semaines": 9,
        "jours_retenus": ["Mardi","Vendredi","Dimanche"],
        "jours_relatifs": {
            "Mardi": 1,
            "Vendredi": 2,
            "Dimanche": 3
        },
        "weeks": [
            {
                "semaine": 1,
                "phase": "Prépa générale",
                "phase_distance": "10K",
                "phase_index": 1,
                "slots": [
                    {"jour": "Mardi", "jour_relatif": 1},
                    {"jour": "Vendredi", "jour_relatif": 2},
                    {"jour": "Dimanche", "jour_relatif": 3}
                ]
            },
            ...
        ]
    }
    """
    status = step3_data.get("status", "ok")
    if status != "ok":
        # On ne construit rien si Step3 n'est pas ok
        log_info(
            f"STEP4/Running → Step3.status={status}, aucun squelette généré",
            module="SCN_1",
        )
        return {
            "status": "skipped",
            "reason": f"Step3.status={status}",
        }

    plan_distance = step3_data.get("plan_distance")
    plan_nb_semaines_raw = step3_data.get("plan_nb_semaines") or 0
    try:
        plan_nb_semaines = int(plan_nb_semaines_raw)
    except (TypeError, ValueError):
        plan_nb_semaines = 0

    phases = step3_data.get("phases") or []

    jours_retenus = step3_data.get("jours_retenus") or []
    if not isinstance(jours_retenus, list):
        # On force un tableau propre
        jours_retenus = [jours_retenus] if jours_retenus else []

    jours_relatifs = _compute_jours_relatifs(jours_retenus)

    log_info(
        f"STEP4/Running → distance={plan_distance}, nb_semaines={plan_nb_semaines}, "
        f"jours_retenus={jours_retenus}, jours_relatifs={jours_relatifs}",
        module="SCN_1",
    )

    if plan_nb_semaines <= 0:
        # Pas de plan, on renvoie une structure minimale
        return {
            "status": "error",
            "reason": "plan_nb_semaines <= 0",
            "plan_distance": plan_distance,
            "plan_nb_semaines": plan_nb_semaines,
            "jours_retenus": jours_retenus,
            "jours_relatifs": jours_relatifs,
            "weeks": [],
        }

    weeks = _build_weeks_from_phases(plan_nb_semaines, phases)

    # Ajout des slots par semaine
    for week in weeks:
        slots: List[Dict[str, Any]] = []
        for jour in jours_retenus:
            jr = jours_relatifs.get(jour)
            slots.append(
                {
                    "jour": jour,
                    "jour_relatif": jr,
                }
            )
        week["slots"] = slots

    return {
        "status": "ok",
        "plan_distance": plan_distance,
        "plan_nb_semaines": plan_nb_semaines,
        "jours_retenus": jours_retenus,
        "jours_relatifs": jours_relatifs,
        "weeks": weeks,
    }
