from core.internal_result import InternalResult
from core.context import SmartCoachContext

from scenarios.socle.scn_0a import run_scn_0a
from scenarios.socle.scn_0b import run_scn_0b
from scenarios.socle.scn_0c import run_scn_0c
from scenarios.socle.scn_0d import run_scn_0d
from scenarios.socle.scn_0e import run_scn_0e
from scenarios.socle.scn_0f import run_scn_0f

from services.airtable_service import AirtableService
from scenarios.extractors import extract_record_fields

from core.utils.logger import log_info, log_warning, log_error


def run_scn_1(context: SmartCoachContext) -> InternalResult:
    """
    SCN_1 → Génération initiale d'un plan Running (structure-only)
    """

    log_info("SCN_1 → Démarrage", module="SCN_1")

    # --------------------------------------------------------------------
    # 1) Lecture du record Airtable
    # --------------------------------------------------------------------
    record_id = context.record_id
    try:
        airtable = AirtableService()
        record = airtable.get_record(record_id)
    except Exception as e:
        log_error(f"Erreur Airtable : {e}", module="SCN_1")
        return InternalResult.error(f"Erreur Airtable : {e}", source="SCN_1")

    if not record:
        log_warning("Record Airtable introuvable ou vide", module="SCN_1")
        return InternalResult.error("Record Airtable introuvable ou vide", source="SCN_1")

    log_info(f"SCN_1 → Lecture record Airtable OK : {record_id}", module="SCN_1")

    # --------------------------------------------------------------------
    # 2) Extraction des champs utiles
    # --------------------------------------------------------------------
    try:
        extracted = extract_record_fields(record)
    except Exception as e:
        log_error(f"Erreur extractors : {e}", module="SCN_1")
        return InternalResult.error(f"Erreur extractors : {e}", source="SCN_1")

    context.update(extracted)

    # --------------------------------------------------------------------
    # 3) SCN_0a — Validation & normalisation
    # --------------------------------------------------------------------
    log_info("SCN_1 → Étape 1 : Validation & normalisation (SCN_0a)", module="SCN_1")
    res_a = run_scn_0a(context)
    if res_a.status != "ok":
        return res_a
    context.update(res_a.data)

    # --------------------------------------------------------------------
    # 4) SCN_0b — Optimisation des jours
    # --------------------------------------------------------------------
    log_info("SCN_1 → Étape 2 : Optimisation des jours (SCN_0b)", module="SCN_1")

    res_b = run_scn_0b(
        context.jours_user_raw,
        getattr(context, "jours_proposes", None),
        getattr(context, "jours_min", None),
        getattr(context, "jours_max", None)
    )
    if res_b.status != "ok":
        return res_b
    context.update(res_b.data)

    # --------------------------------------------------------------------
    # 5) SCN_0c — Calcul VDOT
    # --------------------------------------------------------------------
    log_info("SCN_1 → Étape 3 : Calcul VDOT (SCN_0c)", module="SCN_1")
    res_c = run_scn_0c(context)
    if res_c.status != "ok":
        return res_c
    context.update(res_c.data)

    # --------------------------------------------------------------------
    # 6) SCN_0d — Structure brute
    # --------------------------------------------------------------------
    log_info("SCN_1 → Étape 4 : Structure brute (SCN_0d)", module="SCN_1")
    res_d = run_scn_0d(context)
    if res_d.status != "ok":
        return res_d
    context.update(res_d.data)

    # --------------------------------------------------------------------
    # 7) SCN_0e — Application des phases
    # --------------------------------------------------------------------
    log_info("SCN_1 → Étape 5 : Phases du plan (SCN_0e)", module="SCN_1")
    res_e = run_scn_0e(context)
    if res_e.status != "ok":
        return res_e
    context.update(res_e.data)

    # --------------------------------------------------------------------
    # 8) SCN_0f — JSON final
    # --------------------------------------------------------------------
    log_info("SCN_1 → Étape 6 : Construction JSON final (SCN_0f)", module="SCN_1")
    res_f = run_scn_0f(context)
    if res_f.status != "ok":
        return res_f

    log_info("SCN_1 → OK (plan généré)", module="SCN_1")
    return res_f
