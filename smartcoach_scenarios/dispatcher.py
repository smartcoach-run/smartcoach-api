# smartcoach_scenarios/dispatcher.py
# ===============================================================
# Dispatcher principal des scénarios SmartCoach.
# Pour l’instant :
#   - supporte SCN_1
#   - gère le LogContext (création, durée, statut)
#   - délègue l’enregistrement à log_service.save_log_context
# ===============================================================

from datetime import datetime

from smartcoach_services.log_service import create_log_context, save_log_context
from smartcoach_core.config import SMARTCOACH_DEBUG


def dispatch_scenario(ctx: dict):
    """
    Point d’entrée unique pour lancer un scénario SmartCoach.

    ctx doit contenir :
        - record_id
        - scenario_id
        - airtable
        - fields (champs Airtable du coureur)
        - debug (bool)
    """

    record_id = ctx.get("record_id")
    scenario_id = ctx.get("scenario_id") or "SCN_1"
    airtable = ctx.get("airtable")
    debug = ctx.get("debug", False)

    if SMARTCOACH_DEBUG or debug:
        print(f"[DISPATCHER] Lancement scénario {scenario_id} pour record_id={record_id}")

    # ------------------------------------------------------------------
    # 1. Création du LogContext
    # ------------------------------------------------------------------
    log = create_log_context(record_id=record_id, scenario_id=scenario_id, debug=debug)
    ctx["log"] = log

    start = datetime.utcnow()

    try:
        # ------------------------------------------------------------------
        # 2. Sélection du scénario
        # ------------------------------------------------------------------
        if scenario_id == "SCN_1":
            from smartcoach_scenarios.scn_1 import scenario_1
            result = scenario_1(ctx)
        else:
            raise ValueError(f"Scénario inconnu : {scenario_id}")

        # ------------------------------------------------------------------
        # 3. Mise à jour du log en cas de succès
        # ------------------------------------------------------------------
        end = datetime.utcnow()
        duration = (end - start).total_seconds()

        log["meta"]["ended_at"] = end.iso8601() if hasattr(end, "iso8601") else end.isoformat()
        log["meta"]["duration_sec"] = duration

        log["status"]["statut_execution"] = "OK"
        if not log["status"].get("message"):
            log["status"]["message"] = f"Scénario {scenario_id} exécuté avec succès"

        # Clé de diagnostic standard
        log["tech"]["cle_diagnostic"] = f"{scenario_id} - {record_id}"

        # Sauvegarde dans Airtable
        save_log_context(airtable, log)

        return result

    except Exception as e:
        # ------------------------------------------------------------------
        # 4. Mise à jour du log en cas d’erreur
        # ------------------------------------------------------------------
        end = datetime.utcnow()
        duration = (end - start).total_seconds()

        if log:
            log["meta"]["ended_at"] = end.isoformat()
            log["meta"]["duration_sec"] = duration

            log["status"]["statut_execution"] = "ERROR"
            log["status"]["message"] = f"Erreur scénario {scenario_id}"
            log["status"]["erreur_code"] = None  # pourra être affiné plus tard

            log["tech"]["cle_diagnostic"] = f"{scenario_id} - {record_id}"

            save_log_context(airtable, log)

        if SMARTCOACH_DEBUG or debug:
            print(f"[DISPATCHER] Erreur dans le scénario {scenario_id} :", e)

        # On remonte l'erreur pour que l'API puisse répondre en conséquence
        raise
