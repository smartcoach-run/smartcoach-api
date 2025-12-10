from core.internal_result import InternalResult
from core.utils.logger import log_info, log_error

from scenarios.agregateur.scn_run import run_scn_run
from scenarios.agregateur.scn_7 import run_scn_7


def run_scn_6(context):
    """
    SCN_6 — Orchestrateur RUN
    Collecte le run_context, transmet à SCN_RUN,
    puis appelle SCN_7 pour stocker les résultats.
    """
    log_info("[SCN_6] Début SCN_6 (orchestrateur)")
    log_info(f"[SCN_6] FILE PATH = {__file__}")

    payload = getattr(context, "payload", {}) or {}
    run_context = payload.get("run_context", {})
    mode = payload.get("mode", "ondemand")

    record_id = getattr(context, "record_id", None)
    slot_in = run_context.get("slot", {})

    # NOUVEAU run_context final transmis au moteur
    enriched_run_context = {
        **run_context,  # CONSERVER profile, objectif, slot, historique
        "mode": mode,
        "record_id": record_id,
        "slot_id": slot_in.get("slot_id"),
    }

    scn_run_ctx = InternalResult.ok(
        message="[SCN_6] Contexte SCN_RUN enrichi",
        data={},
        source="SCN_6"
    )
    scn_run_ctx.record_id = record_id
    scn_run_ctx.payload = {"run_context": enriched_run_context}

    log_info(f"[SCN_6] run_context transmis à SCN_RUN = {list(enriched_run_context.keys())}")

    # --------------------
    # APPEL SCN_RUN
    # --------------------
    scn_run_result = run_scn_run(scn_run_ctx)

    if scn_run_result.status == "error":
        log_error(f"[SCN_6] Erreur SCN_RUN : {scn_run_result.message}")
        return InternalResult.error(
            message=f"Erreur SCN_RUN dans SCN_6 : {scn_run_result.message}",
            source="SCN_6",
            data={"scn_run_error": scn_run_result.data}
        )

    scn_run_data = scn_run_result.data or {}
    session = scn_run_data.get("session")
    slot = scn_run_data.get("slot")
    war_room = scn_run_data.get("war_room")
    phase_context = scn_run_data.get("phase_context")
    ics_block = scn_run_data.get("ics_block")

    # --------------------
    # APPEL SCN_7 (stockage Airtable)
    # --------------------
    scn7_ctx = InternalResult.ok(
        message="[SCN_6] Contexte SCN_7 préparé",
        data={},
        source="SCN_6"
    )
    scn7_ctx.record_id = record_id
    scn7_ctx.slot = slot or slot_in
    scn7_ctx.session = session
    scn7_ctx.war_room = war_room
    scn7_ctx.phase_context = phase_context

    scn7_result = run_scn_7(scn7_ctx)

    if scn7_result.status == "error":
        log_error(f"[SCN_6] Erreur SCN_7 : {scn7_result.message}")
        return InternalResult.error(
            message=f"Erreur SCN_7 : {scn7_result.message}",
            source="SCN_6",
            data={"storage_error": scn7_result.data}
        )

    # OK FINAL
    return InternalResult.ok(
        message="SCN_6 exécuté avec succès",
        source="SCN_6",
        data={
            "session": session,
            "slot": slot,
            "war_room": war_room,
            "phase_context": phase_context,
            "ics_block": ics_block,
            "storage": scn7_result.data,
        }
    )
