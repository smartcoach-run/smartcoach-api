# SCN_1.py (version corrigée – chaînage SOCLE propre)

from core.internal_result import InternalResult
from core.context import SmartCoachContext
from core.utils.logger import get_logger
from services.airtable_service import AirtableService
from scenarios.extractors import extract_record_fields
from scenarios.socle.scn_0a import run_scn_0a
from scenarios.socle.scn_0b import run_scn_0b
from scenarios.socle.scn_0c import run_scn_0c
from scenarios.socle.scn_0d import run_scn_0d
from scenarios.socle.scn_0e import run_scn_0e
from scenarios.socle.scn_0f import run_scn_0f  # conservé si utilisé ailleurs
from scenarios.builders import build_step3_running, build_step4_running
from services.airtable_tables import ATABLES
from services.airtable_fields import ATFIELDS

log = get_logger("SCN_1")


def run_scn_1(context: SmartCoachContext) -> InternalResult:
    service = AirtableService()

    # -----------------------------------
    # Étape 0 — Chargement record brut
    # -----------------------------------
    if context.record_raw is None:
        record = service.get_record(context.record_id)
        if record is None:
            return InternalResult.make_error(
                "Record Airtable vide ou introuvable",
                source="SCN_1",
            )
        context.record_raw = record

    # -----------------------------------
    # Étape 1 : SCN_0a — Normalisation
    # -----------------------------------
    log.info("SCN_1 → Étape 1 : Normalisation")
    res_a = run_scn_0a(context)
    if not res_a.success:
        return res_a
    context.record_norm = res_a.data
    context.update(res_a.data)

    # -----------------------------------
    # Étape 1bis : Chargement Référence Jours
    # -----------------------------------
    ref_ids = context.record_raw.get("fields", {}).get("⚖️ Référence Jours", [])
    if ref_ids:
        ref_id = ref_ids[0]
        service.set_table(ATABLES.REF_JOURS)
        ref_record = service.get_record(ref_id)
        if ref_record and "fields" in ref_record:
            ref_fields = ref_record["fields"]
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

    # -----------------------------------
    # Étape 2 : SCN_0b — Optimisation des jours
    # -----------------------------------
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

    # On propage le résultat SOCLE dans le contexte
    context.update(res_b.data)
    jours_valides = res_b.data.get("jours_result", {}).get("jours_valides", [])
    if not jours_valides:
        return InternalResult.make_error(
            "SCN_0b n'a retourné aucun jour valide",
            source="SCN_1",
        )

    # -----------------------------------
    # Étape 3 : SCN_0c — Calcul VDOT
    # -----------------------------------
    log.info("SCN_1 → Étape 3 : Calcul VDOT (SCN_0c)")
    res_c = run_scn_0c(context, jours_valides)
    if not res_c.success:
        return res_c
    context.update({"vdot_result": res_c.data})

    # ==================================================================
    #  Étape 4 : Step3 — Construction données semaine-type (Running)
    # ==================================================================
    log.info("SCN_1 → Étape 4 : Step3 — Construction données semaine-type")
    try:
        # On passe TOUT le payload de SCN_0b à Step3 pour qu'il réutilise
        # directement jours_result.jours_valides (source de vérité SOCLE).
        step3_data = build_step3_running(context.record_raw, res_b.data)
    except Exception as e:
        return InternalResult.make_error(f"Erreur Step3 : {e}", source="SCN_1")

    # nb_semaines canonique : priorité à une éventuelle valeur calculée,
    # sinon nb_semaines du plan.
    nb_semaines = (
        step3_data.get("nb_semaines_calculees")
        or step3_data.get("plan_nb_semaines")
    )
    if not nb_semaines:
        return InternalResult.make_error(
            "plan_nb_semaines absent après Step3",
            source="SCN_1",
        )

    context.update(
        {
            "plan_nb_semaines": nb_semaines,
            "step3": step3_data,
        }
    )

    # ==================================================================
    #  Étape 5 : Step4 — Répartition hebdomadaire (squelette)
    # ==================================================================
    log.info("SCN_1 → Étape 5 : Step4 — Répartition hebdomadaire")
    try:
        step4_data = build_step4_running(step3_data)
    except Exception as e:
        return InternalResult.make_error(f"Erreur Step4 : {e}", source="SCN_1")

    context.update({"week_structure": step4_data})

    # -----------------------------------
    # Étape 6 : SCN_0d — Structure brute (slots)
    # -----------------------------------
    log.info("SCN_1 → Étape 6 : SCN_0d — Génération slots")

    # Ici on s'appuie sur les jours retenus / relatifs issus de Step4,
    # qui eux-mêmes dérivent de SCN_0b (via Step3).
    jours_retenus = step4_data.get("jours_retenus", [])
    jours_relatifs = step4_data.get("jours_relatifs", {})

    try:
        slots = run_scn_0d(jours_retenus, jours_relatifs, nb_semaines)
    except Exception as e:
        return InternalResult.make_error(f"Erreur SCN_0d : {e}", source="SCN_1")

    context.update({"slots": slots})

    # -----------------------------------
    # Étape 7 : SCN_0e — Attribution des phases
    # -----------------------------------
    log.info("SCN_1 → Étape 7 : SCN_0e — Attribution phases")
    try:
        phases = run_scn_0e(slots, nb_semaines)
    except Exception as e:
        return InternalResult.make_error(f"Erreur SCN_0e : {e}", source="SCN_1")

    context.update({"phases": phases})

    # -----------------------------------
    # Sortie standardisée SCN_1
    # -----------------------------------
    return InternalResult.make_success(
        message="SCN_1 terminé (version corrigée)",
        data={
            "vdot": context.vdot_result,
            "plan_nb_semaines": nb_semaines,
            "week_structure": step4_data,
            "slots": slots,
            "phases": phases,
        },
        context=context,
        source="SCN_1",
    )
