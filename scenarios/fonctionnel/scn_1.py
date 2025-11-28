from core.internal_result import InternalResult
from core.context import SmartCoachContext
from core.utils.logger import get_logger
from services.airtable_service import AirtableService
from scenarios.extractors import extract_record_fields
from scenarios.socle.scn_0a import run_scn_0a
from scenarios.socle.scn_0b import run_scn_0b
from scenarios.socle.scn_0c import run_scn_0c

log = get_logger("SCN_1")


def run_scn_1(context: SmartCoachContext) -> InternalResult:

    log.info("SCN_1 → Étape 1 : Validation & normalisation (SCN_0a)")
    res_a = run_scn_0a(context)

    if not res_a.success:
        return res_a

    context.update(res_a.data)

    # --------------------------
    # Étape 2 : Optimisation jours
    # --------------------------
    log.info("SCN_1 → Étape 2 : Optimisation des jours (SCN_0b)")

    res_b = run_scn_0b(
        context.jours_result,
        getattr(context, "jours_proposes", None),
        getattr(context, "jours_min", None),
        getattr(context, "jours_max", None)
    )

    if not res_b.success:
        return res_b

    context.update(res_b.data)

    # --------------------------
    # Étape 3 : VDOT / semaine-type
    # --------------------------
    log.info("SCN_1 → Étape 3 : Calcul VDOT (SCN_0c)")

    jours_final = context.jours_result.get("jours_valides", [])
    res_c = run_scn_0c(context, jours_final)

    if not res_c.success:
        return res_c

    context.update({"vdot_result": res_c.data})

    # --------------------------
    # Succès final
    # --------------------------
    return InternalResult.make_success(
        message="SCN_1 terminé",
        data={"vdot": context.vdot_result},
        context=context,
        source="SCN_1"
    )
