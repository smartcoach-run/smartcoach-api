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
    # INSTANCE RÉUTILISABLE
    service = AirtableService()

    # 🔥 Étape 0 : Charger le record Airtable si absent
    if context.record_raw is None:
        record = service.get_record(context.record_id)
        if record is None:
            return InternalResult.make_error(
                message="Record Airtable vide ou introuvable",
                source="SCN_1"
            )
        context.record_raw = record

    # -----------------------------------
    # Étape 1 : SCN_0a
    # -----------------------------------
    log.info("SCN_1 → Étape 1 : Validation & normalisation (SCN_0a)")
    # Étape 1 : Normalisation via SCN_0a
    log.info("SCN_1 → Étape 1 : Validation & normalisation (SCN_0a)")
    res_a = run_scn_0a(context)

    if not res_a.success:
        return res_a

    # SCN_0a renvoie directement les champs normalisés dans res_a.data
    context.record_norm = res_a.data
    context.update(res_a.data)

    log.info(f"DEBUG SCN_1 → CONTEXT APRÈS SCN_0a : {context.record_norm}")

    # ============================================================
    # Étape 1bis : Chargement de la table "Référence Jours"
    # ============================================================

    from services.airtable_tables import ATABLES

    ref_ids = context.record_raw.get("fields", {}).get("⚖️ Référence Jours", [])

    if ref_ids:
        ref_id = ref_ids[0]

        service.set_table(ATABLES.REF_JOURS)  # <-- CORRECTION ICI

        ref_record = service.get_record(ref_id)

        if ref_record and "fields" in ref_record:
            ref_fields = ref_record["fields"]

            # on stocke dans le contexte pour SCN_0b
            context.jours_min_ref = ref_fields.get("Nb_jours_min")
            context.jours_max_ref = ref_fields.get("Nb_jours_max")
            context.jours_proposes_ref = ref_fields.get("Jours_proposés")
            context.esp_min = ref_fields.get("espacement_min")
            context.esp_max = ref_fields.get("espacement_max")

        else:
            context.jours_min_ref = None
            context.jours_max_ref = None
            context.jours_proposes_ref = None
            context.esp_min = None
            context.esp_max = None
    else:
        context.jours_min_ref = None
        context.jours_max_ref = None
        context.jours_proposes_ref = None
        context.esp_min = None
        context.esp_max = None


    log.debug(f"DEBUG SCN_1 → jours_proposes_ref = {context.jours_proposes_ref}", module="SCN_1")

    # Étape 2 : Optimisation jours
    log.info("SCN_1 → Étape 2 : Optimisation des jours (SCN_0b)")

    res_b = run_scn_0b(
        jours_user_raw=context.record_norm.get("jours_disponibles"),
        jours_proposes=context.jours_proposes_ref,
        jours_min=context.jours_min_ref,
        jours_max=context.jours_max_ref,
        esp_min=context.esp_min,
        esp_max=context.esp_max,
    )

    if not res_b.success:
        return res_b

    if not res_b.data or "jours_result" not in res_b.data:
        return InternalResult.make_error(
            message="SCN_0b n’a pas renvoyé 'jours_result'",
            context=context,
            source="SCN_1"
        )

    context.update(res_b.data)

    # --------------------------
    # Étape 3 : VDOT / semaine-type
    # --------------------------
    jours_final = context.jours_result.get("jours_valides", [])
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
