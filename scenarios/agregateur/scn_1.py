# ---------------------------------------------------------
# SCN_1 – Génération de la structure de plan (STATELESS OK)
# ---------------------------------------------------------

from datetime import date, datetime, timedelta
from core.internal_result import InternalResult
from core.utils.logger import get_logger

from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES

from scenarios.socle.scn_0a import run_scn_0a
from scenarios.socle.scn_0b import run_scn_0b
from scenarios.socle.scn_0c import run_scn_0c

log = get_logger("SCN_1")

# ---------------------------------------------------------
# Helpers dates
# ---------------------------------------------------------

def _parse_iso_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        return None


# ---------------------------------------------------------
# Fenêtre d'entraînement (version contractuelle)
# ---------------------------------------------------------

RUN_DISTANCE_CONFIG = {
    "5K":  {"min": 6,  "max": 16, "base": 10},
    "10K": {"min": 8,  "max": 20, "base": 12},
    "HM":  {"min": 10, "max": 24, "base": 14},
    "M":   {"min": 12, "max": 28, "base": 18},
}

LEVEL_ADJUST = {
    "Débutant": 2,
    "Reprise": 1,
    "Intermédiaire": 0,
    "Confirmé": -1,
    "Expert": -2,
}

DEFAULT_WEEKS = {
    "VTL": 12,
    "KIDS": 8,
    "HYROX": 16,
}


def _compute_training_window(data):
    mode = data.get("mode")
    objectif = (data.get("objectif") or "").upper()
    niveau = data.get("niveau_final") or data.get("niveau") or "Débutant"

    today = date.today()
    date_obj = _parse_iso_date(data.get("date_objectif"))
    date_anchor = _parse_iso_date(data.get("date_derniere_demande")) or today

    if date_obj and date_obj > today:
        date_fin = date_obj
    else:
        date_fin = date_anchor

    if mode == "RUN" and objectif in RUN_DISTANCE_CONFIG:
        cfg = RUN_DISTANCE_CONFIG[objectif]
        base = cfg["base"] + LEVEL_ADJUST.get(niveau, 0)
        nb_semaines = max(cfg["min"], min(base, cfg["max"]))
    else:
        nb_semaines = DEFAULT_WEEKS.get(mode, 8)

    date_debut = date_fin - timedelta(weeks=nb_semaines)

    return {
        "nb_semaines": nb_semaines,
        "date_debut_plan": date_debut.isoformat(),
        "date_fin_plan": date_fin.isoformat(),
        "warnings": [],
    }


def _build_plan_skeleton(nb_semaines, jours_optimises):
    return {
        f"S{i}": {jour: None for jour in jours_optimises}
        for i in range(1, nb_semaines + 1)
    }


# ---------------------------------------------------------
# SCN_1 – ENTRY POINT
# ---------------------------------------------------------

def run_scn_1(context):
    """
    Deux modes explicites :
    - mode = 'airtable' (défaut) → lecture Airtable
    - mode = 'structure_only' → aucune dépendance externe
    """

    payload = context.payload or {}
    mode = payload.get("mode", "airtable")

    # =====================================================
    # MODE STRUCTURE ONLY (utilisé par SCN_2, Make, tests)
    # =====================================================
    if mode == "structure_only":
        log.info("SCN_1 → mode STRUCTURE_ONLY")

        data = payload.get("data") or {}

    # =====================================================
    # MODE AIRTABLE (appel historique)
    # =====================================================
    else:
        log.info("SCN_1 → mode AIRTABLE")

        if not context.record_id:
            return InternalResult.error(
                message="record_id manquant pour SCN_1 (mode airtable)",
                source="SCN_1",
                context=context,
            )

        service = AirtableService()
        record = service.get_record(ATABLES.COU_TABLE, context.record_id)

        if not record:
            return InternalResult.error(
                message=f"Record introuvable : {context.record_id}",
                data={"code": "KO_TECH"},
                source="SCN_1",
                context=context,
            )

        norm = run_scn_0a(context, record)
        if norm["status"] != "ok":
            return norm

        data = norm["data"]

        level = run_scn_0c(context, data)
        if level["status"] != "ok":
            return level
        data.update(level["data"])

        days = run_scn_0b(context, data)
        if days["status"] != "ok":
            return days
        data.update(days["data"])

    # =====================================================
    # PIPELINE COMMUN
    # =====================================================

    window = _compute_training_window(data)
    data.update(window)

    plan_squelette = _build_plan_skeleton(
        data["nb_semaines"],
        data.get("jours_optimises", []),
    )

    return InternalResult.ok(
        data={
            "nb_semaines": data["nb_semaines"],
            "date_debut_plan": data["date_debut_plan"],
            "date_fin_plan": data["date_fin_plan"],
            "jours_optimises": data.get("jours_optimises", []),
            "plan_squelette": plan_squelette,
        },
        message="SCN_1 terminé (structure générée)",
        source="SCN_1",
        context=context,
    )
