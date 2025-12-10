# ---------------------------------------------------------
# SCN_1 – Orchestration du pipeline principal (from scratch)
# ---------------------------------------------------------
from datetime import date, datetime, timedelta

from core.internal_result import InternalResult
from core.utils.logger import get_logger
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES

from scenarios.socle.scn_0a import run_scn_0a
from scenarios.socle.scn_0c import run_scn_0c
from scenarios.socle.scn_0b import run_scn_0b

# ---------------------------------------------------------
# Config SmartCoach – Fenêtres d'entraînement (mode C)
# ---------------------------------------------------------

RUN_DISTANCE_CONFIG = {
    "5K":  {"min_weeks": 6,  "max_weeks": 16, "base_weeks": 10},
    "10K": {"min_weeks": 8,  "max_weeks": 20, "base_weeks": 12},
    "HM":  {"min_weeks": 10, "max_weeks": 24, "base_weeks": 14},
    "M":   {"min_weeks": 12, "max_weeks": 28, "base_weeks": 18},
}

LEVEL_ADJUST = {
    "Débutant": 2,
    "Reprise": 1,
    "Intermédiaire": 0,
    "Confirmé": -1,
    "Expert": -2,
}

DEFAULT_CONFIG_OTHER = {
    "VTL": 12,   # Vitalité : 12 semaines par défaut
    "KIDS": 8,   # Kids : 8 semaines
    "HYROX": 16  # Hyrox / DEKA : 16 semaines
}

log = get_logger("SCN_1")

def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        return None


def _compute_training_window(data: dict, context) -> dict:
    """
    Step3 – Calcule nb_semaines + date_debut_plan + date_fin_plan
    en fonction de :
      - mode (RUN / VTL / KIDS / HYROX)
      - objectif (5K, 10K, HM, M, etc.)
      - niveau_final (ou niveau)
      - date_objectif (si dispo)
    """
    mode = data.get("mode")
    objectif = (data.get("objectif") or "").upper()
    niveau_final = data.get("niveau_final") or data.get("niveau") or "Débutant"
    date_obj_str = data.get("date_objectif")

    today = getattr(context, "ref_date", date.today())
    target_date = _parse_iso_date(date_obj_str)

    nb_semaines = None
    warnings: list[str] = []

    # ---- Cas RUN (5K / 10K / HM / M) ----
    if mode == "RUN" and objectif in RUN_DISTANCE_CONFIG:
        cfg = RUN_DISTANCE_CONFIG[objectif]

        base = cfg["base_weeks"] + LEVEL_ADJUST.get(niveau_final, 0)
        base = max(cfg["min_weeks"], min(base, cfg["max_weeks"]))

        if target_date:
            delta_days = (target_date - today).days

            if delta_days <= 0:
                warnings.append("date_objectif_passee")
                nb_semaines = cfg["min_weeks"]
                date_fin_plan = today
                date_debut_plan = today - timedelta(weeks=nb_semaines)
            else:
                # nombre maximal de semaines possible avant la course
                max_weeks_by_date = max(1, delta_days // 7)

                # on reste dans la fenêtre min/max de la config
                nb_semaines = min(base, max_weeks_by_date, cfg["max_weeks"])

                # si la course est très proche, plan tronqué
                if max_weeks_by_date < cfg["min_weeks"]:
                    warnings.append("plan_tronque_court")

                date_fin_plan = target_date
                date_debut_plan = target_date - timedelta(weeks=nb_semaines)
        else:
            # pas de date => plan générique
            nb_semaines = base
            date_debut_plan = today
            date_fin_plan = today + timedelta(weeks=nb_semaines)

    else:
        # ---- Cas autres modes (Vitalité / Kids / Hyrox) ----
        default_weeks = DEFAULT_CONFIG_OTHER.get(mode, 8)
        nb_semaines = default_weeks

        if target_date:
            delta_days = (target_date - today).days
            if delta_days > 0:
                max_weeks_by_date = max(1, delta_days // 7)
                nb_semaines = min(default_weeks, max_weeks_by_date)
                if max_weeks_by_date < default_weeks:
                    warnings.append("plan_tronque_court")
                date_fin_plan = target_date
                date_debut_plan = target_date - timedelta(weeks=nb_semaines)
            else:
                warnings.append("date_objectif_passee")
                date_debut_plan = today
                date_fin_plan = today + timedelta(weeks=nb_semaines)
        else:
            date_debut_plan = today
            date_fin_plan = today + timedelta(weeks=nb_semaines)

    return {
        "nb_semaines": nb_semaines,
        "date_debut_plan": date_debut_plan.isoformat(),
        "date_fin_plan": date_fin_plan.isoformat(),
        "warnings": warnings
    }
# Step3 — Fenêtre d'entraînement SmartCoach (version contractuelle)
def _compute_training_window(data: dict, context=None) -> dict:
    """
    Version tolérante :
    - Si date_objectif > today → c'est une course
    - Sinon → on démarre le plan à partir de Date_dernière_demande
    """

    objectif = (data.get("objectif") or "").upper()
    mode = data.get("mode")
    niveau_final = data.get("niveau_final") or "Débutant"

    today = date.today()

    # 1) Charger les deux dates
    date_obj = _parse_iso_date(data.get("date_objectif"))
    date_anchor = _parse_iso_date(data.get("date_derniere_demande")) or today

    # 2) Déterminer la vraie date de fin utilisée
    if date_obj and date_obj > today:
        date_fin = date_obj                 # cas RUN normal
    else:
        date_fin = date_anchor              # cas "pas de course" / "date passée"

    # 3) Nombre de semaines selon ce que tu avais avant
    if mode == "RUN" and objectif in RUN_DISTANCE_CONFIG:
        cfg = RUN_DISTANCE_CONFIG[objectif]
        base = cfg["base_weeks"] + LEVEL_ADJUST.get(niveau_final, 0)
        nb_semaines = max(cfg["min_weeks"], min(base, cfg["max_weeks"]))
    else:
        nb_semaines = DEFAULT_CONFIG_OTHER.get(mode, 8)

    # 4) Date de début
    date_debut = date_fin - timedelta(weeks=nb_semaines)

    return {
        "nb_semaines": nb_semaines,
        "date_debut_plan": date_debut.isoformat(),
        "date_fin_plan": date_fin.isoformat(),
        "warnings": []
    }

def _build_plan_skeleton(nb_semaines: int, jours_optimises: list[str]) -> dict:
    """
    Step4 – Construit le squelette de plan :
    {
      "S1": {"Mardi": null, "Jeudi": null, "Dimanche": null},
      "S2": {...},
      ...
    }
    """
    structure: dict[str, dict] = {}

    for week_idx in range(1, nb_semaines + 1):
        code = f"S{week_idx}"
        structure[code] = {jour: None for jour in jours_optimises}

    return structure

def run_scn_1(context) -> dict:
    # 1) Lecture Airtable
    log.info("SCN_1 → Étape 1 : Lecture Airtable")

    service = AirtableService()
    course_record = service.get_record(
        ATABLES.COU_TABLE,
        context.record_id
    )

    if not course_record:
        return InternalResult.error(
            message=f"Record introuvable : {context.record_id}",
            data={"code": "KO_TECH"},
            context=context,
            source="SCN_1"
)

    # 2) SCN_0a — normalisation
    log.info("SCN_1 → Étape 2 : Normalisation (SCN_0a)")
    norm = run_scn_0a(context, course_record)

    if norm["status"] != "ok":
        return norm  # on remonte tel quel le KO_DATA

    data = norm["data"]

    # 3) SCN_0c — niveau & VDOT
    log.info("SCN_1 → Étape 3 : Niveau & VDOT (SCN_0c)")
    level = run_scn_0c(context, data)

    if level["status"] != "ok":
        return level

    data.update(level["data"])

    # 4) SCN_0b — optimisation jours
    log.info("SCN_1 → Étape 4 : Optimisation jours (SCN_0b)")
    days = run_scn_0b(context, data)

    if days["status"] != "ok":
        return days

    data.update(days["data"])  # ajoute jours_optimises

    # 5) Step3 — Fenêtre d'entraînement (nb_semaines + dates)
    log.info("SCN_1 → Étape 5 : Calcul fenêtre (Step3)")
    window = _compute_training_window(data, context)

    data["nb_semaines"] = window["nb_semaines"]
    data["date_debut_plan"] = window["date_debut_plan"]
    data["date_fin_plan"] = window["date_fin_plan"]
    data["warnings"] = window["warnings"]

    # 6) Step4 — Squelette de plan
    log.info("SCN_1 → Étape 6 : Construction squelette (Step4)")
    plan_squelette = _build_plan_skeleton(
        nb_semaines=data["nb_semaines"],
        jours_optimises=data["jours_optimises"]
    )
    data["plan_squelette"] = plan_squelette

    # 7) Sortie finale SCN_1 (MVP minimal, aucun slot écrit dans Airtable)
    return InternalResult.ok(
        data={
            "nb_semaines": data["nb_semaines"],
            "date_debut_plan": data["date_debut_plan"],
            "date_fin_plan": data["date_fin_plan"],
            "jours_optimises": data["jours_optimises"],
            "plan_squelette": data["plan_squelette"]
        },
        message="SCN_1 terminé (structure générée sans écriture Airtable)",
        source="SCN_1",
        context=context
    )
