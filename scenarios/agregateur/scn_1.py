# ================================================================
#  SCN_1 — Génération de plan Running (version stabilisée v2025)
# ================================================================

from core.internal_result import InternalResult
from core.context import SmartCoachContext
from core.utils.logger import get_logger
from services.airtable_service import AirtableService
from services.airtable_tables import ATABLES
from scenarios.socle.scn_0a import run_scn_0a
from scenarios.socle.scn_0b import run_scn_0b
from scenarios.socle.scn_0d import run_scn_0d
from scenarios.socle.scn_0e import run_scn_0e
from scenarios.builders import build_step3_running, build_step4_running

log = get_logger("SCN_1")


def run_scn_1(context: SmartCoachContext) -> InternalResult:

    service = AirtableService()

    # ------------------------------------------------------------
    # 0) Chargement record brut Airtable
    # ------------------------------------------------------------
    if context.record_raw is None:
        record = service.get_record(context.record_id)
        if record is None:
            return InternalResult.make_error(
                "Record Airtable vide ou introuvable",
                source="SCN_1",
            )
        context.record_raw = record

    # ------------------------------------------------------------
    # 1) SCN_0a — Normalisation Fillout/Airtable
    # ------------------------------------------------------------
    log.info("SCN_1 → Étape 1 : Normalisation (SCN_0a)")
    res_a = run_scn_0a(context)
    if not res_a.success:
        return res_a

    # Propagation valeurs normalisées
    context.record_norm = res_a.data
    context.update(res_a.data)
    # Harmonisation objectif (singulier)
    if "objectifs" in context.__dict__ and context.objectifs:
        # On prend le premier élément
        context.objectif = context.objectifs[0]


    # ------------------------------------------------------------
    # 1bis) Chargement Référence Jours (si présente)
    # ------------------------------------------------------------
    ref_ids = context.record_raw.get("fields", {}).get("⚖️ Référence Jours", [])
    if ref_ids:
        ref_id = ref_ids[0]
        service.set_table(ATABLES.REF_JOURS)
        ref_record = service.get_record(ref_id)
        ref = ref_record.get("fields", {}) if ref_record else {}

        context.jours_min_ref = ref.get("Nb_jours_min")
        context.jours_max_ref = ref.get("Nb_jours_max")
        context.jours_proposes_ref = ref.get("Jours_proposés")
        context.esp_min = ref.get("espacement_min")
        context.esp_max = ref.get("espacement_max")
    else:
        context.jours_min_ref = None
        context.jours_max_ref = None
        context.jours_proposes_ref = None
        context.esp_min = None
        context.esp_max = None

    # ------------------------------------------------------------
    # 2) SCN_0b — Optimisation des jours
    # ------------------------------------------------------------
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

    context.update(res_b.data)
    jours_valides = res_b.data.get("jours_result", {}).get("jours_valides", [])

    if not jours_valides:
        return InternalResult.make_error(
            "Aucun jour valide après SCN_0b",
            source="SCN_1",
        )

    # ------------------------------------------------------------
    # 3) Step3 — Construction intermédaire Running
    # ------------------------------------------------------------
    log.info("SCN_1 → Étape 3 : Step3 (données semaine-type)")
    try:
        step3_data = build_step3_running(context.record_raw, res_b.data)
    except Exception as e:
        return InternalResult.make_error(
            f"Erreur Step3 : {e}", source="SCN_1"
        )

    # Détermination officielle nb_semaines
    nb_semaines = (
        step3_data.get("nb_semaines_calculees")
        or step3_data.get("plan_nb_semaines")
    )

    if not nb_semaines or nb_semaines <= 0:
        return InternalResult.make_error(
            "Durée du plan invalide (nb_semaines ≤ 0)",
            source="SCN_1",
        )

    context.update({
        "plan_nb_semaines": nb_semaines,
        "step3": step3_data,
    })

    # ------------------------------------------------------------
    # 4) Step4 — Répartition hebdomadaire (semaine → slots relatifs)
    # ------------------------------------------------------------
    log.info("SCN_1 → Étape 4 : Step4 (répartition hebdomadaire)")
    try:
        step4_data = build_step4_running(step3_data)
    except Exception as e:
        return InternalResult.make_error(
            f"Erreur Step4 : {e}", source="SCN_1"
        )

    context.update({"week_structure": step4_data})

    # ------------------------------------------------------------
    # 5) SCN_0d — Structure brute des slots
    # ------------------------------------------------------------
    log.info("SCN_1 → Étape 5 : SCN_0d (slots bruts)")

    jours_retenus = step4_data.get("jours_retenus", [])
    jours_relatifs = step4_data.get("jours_relatifs", {})

    try:
        slots = run_scn_0d(jours_retenus, jours_relatifs, nb_semaines)
    except Exception as e:
        return InternalResult.make_error(
            f"Erreur SCN_0d : {e}", source="SCN_1"
        )

    context.update({"slots": slots})
    context.slots_by_week = slots

    # ------------------------------------------------------------
    # 6) SCN_0e — Affectation des phases (progression)
    # ------------------------------------------------------------
    log.info("SCN_1 → Étape 6 : SCN_0e (phases)")
    try:
        phases = run_scn_0e(slots, nb_semaines)
        # ------------------------------------------------------------
        # 6bis) Harmonisation des phases (mapping v2025)
        # ------------------------------------------------------------
        PHASE_MAP = {
            "PHASE 1 — Base": "Prépa générale",
            "PHASE 2 — Développement": "Spécifique",
            "PHASE 3 — Affûtage": "Affûtage",
            "Phase 1 — Base": "Prépa générale",
            "Phase 2 — Développement": "Spécifique",
            "Phase 3 — Affûtage": "Affûtage",
        }

        for p in phases:
            nom = p.get("phase")
            if nom in PHASE_MAP:
                p["phase"] = PHASE_MAP[nom]

    except Exception as e:
        return InternalResult.make_error(
            f"Erreur SCN_0e : {e}", source="SCN_1"
        )
    log.info(f"[SCN_1] SLOTS before update = {slots}")

    context.update({"phases": phases})

    # ------------------------------------------------------------
    # 7) Sortie standardisée SCN_1
    # ------------------------------------------------------------
    return InternalResult.make_success(
        message="SCN_1 terminé avec succès (v2025 stable)",
        data={
            "plan_nb_semaines": nb_semaines,
            "week_structure": step4_data,
            "slots": slots,
            "phases": phases,
        },
        context=context,
        source="SCN_1",
    )