from core.internal_result import InternalResult
from core.utils.logger import log_info, log_error


def run_scn_run(context):
    """
    SCN_RUN — Point d'entrée Running vers le BAB Engine.
    Reçoit context.payload["run_context"] depuis SCN_6.
    """

    # Récupération du payload brut transmis par SCN_6
    raw_payload = getattr(context, "payload", {}) or {}

    # Si SCN_6 a construit un champ "run_context", on le prend en priorité
    run_context = raw_payload.get("run_context") or raw_payload

    log_info(f"[SCN_RUN] run_context keys (avant enrichissement) = {list(run_context.keys())}")

    # 🔹 Sécurisation / enrichissement : on s’assure que slot_id et record_id
    # sont bien présents à plat dans le run_context avant d'appeler le moteur.

    # 1) slot_id : on le récupère depuis run_context["slot"] si besoin
    slot = run_context.get("slot") or {}
    if "slot_id" not in run_context and isinstance(slot, dict):
        slot_id = slot.get("slot_id")
        if slot_id:
            run_context["slot_id"] = slot_id
            log_info(f"[SCN_RUN] slot_id enrichi depuis slot = {slot_id}")

    # 2) record_id : on le récupère depuis le contexte si SCN_6 l’a posé dessus
    if "record_id" not in run_context and hasattr(context, "record_id"):
        record_id = getattr(context, "record_id")
        if record_id:
            run_context["record_id"] = record_id
            log_info(f"[SCN_RUN] record_id enrichi depuis context = {record_id}")

    log_info(f"[SCN_RUN] run_context keys (final) = {list(run_context.keys())}")

    # --------------------------------------------------
    # Sélection du moteur de génération
    # --------------------------------------------------
    engine_version = run_context.get("engine_version")
    mode = run_context.get("profile", {}).get("mode")

    try:
        # 🔵 Nouveau moteur RUNNING (SCN_2) — activé par flag
        if engine_version == "C" and mode == "running":
            log_info("[SCN_RUN] engine_version=C → utilisation SCN_2")
            from scenarios.agregateur.scn_2 import run_scn_2
            result = run_scn_2(context)

        # 🔴 Fallback legacy — BAB_ENGINE_MVP (SCN_0g)
        else:
            log_info("[SCN_RUN] fallback BAB_ENGINE_MVP (SCN_0g)")
            from engine import bab_engine_mvp
            result = bab_engine_mvp.run(run_context)

    except Exception as e:
        log_error(f"[SCN_RUN] Exception moteur : {e}")
        return InternalResult.error(
            message=f"Erreur SCN_RUN : Exception moteur : {e}",
            source="SCN_RUN",
            data={"exception": str(e)},
        )

    # Si le moteur renvoie une erreur, on la remonte telle quelle
    if result.status == "error":
        return result

    # Données renvoyées par le moteur
    data = result.data or {}

    return InternalResult.ok(
        message="[SCN_RUN] Séance générée via BAB_ENGINE_MVP",
        source="SCN_RUN",
        data=data,
    )
