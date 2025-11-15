# smartcoach_scenarios/dispatcher.py
from smartcoach_services.log_service import log_event

def dispatch_scenario(ctx):
    record_id = ctx.get("record_id")
    scenario_id = ctx.get("scenario_id")
    airtable = ctx.get("airtable")

    try:
        # Exécution
        if scenario_id == "SCN_1":
            from smartcoach_scenarios.scn_1 import scenario_1
            result = scenario_1(ctx)
        else:
            raise ValueError(f"Scénario inconnu : {scenario_id}")

        # LOG OK
        log_event(
            airtable=airtable,
            record_id=record_id,
            statut="OK",
            message=f"Scénario {scenario_id} exécuté avec succès",
            environnement="DEV"
        )

        return result

    except Exception as e:
        # LOG ERROR
        log_event(
            airtable=airtable,
            record_id=record_id,
            statut="ERROR",
            message=f"Erreur scénario {scenario_id} : {e}",
            environnement="DEV"
        )

        raise

    record_id = ctx.get("record_id")
    scenario_id = ctx.get("scenario_id")
    debug = ctx.get("debug", False)
    fields = ctx.get("fields", {})
    airtable = ctx.get("airtable")

    # 1. Log : Démarrage
    try:
        log_event(
            airtable=airtable,
            record_id=record_id,
            statut="START",
            message=f"Début scénario {scenario_id}",
            environnement="DEV"
        )
    except Exception as e:
        print("[DISPATCHER] Log START impossible :", e)

    # 2. Sélection du scénario
    if scenario_id == "SCN_1":
        from smartcoach_scenarios.scn_1 import scenario_1
        result = scenario_1(ctx)
    else:
        raise ValueError(f"Scénario inconnu : {scenario_id}")

    # 3. Log : Succès
    try:
        log_event(
            airtable=airtable,
            record_id=record_id,
            statut="OK",
            message=f"Scénario {scenario_id} exécuté avec succès",
            environnement="DEV"
        )
    except Exception as e:
        print("[DISPATCHER] Log OK impossible :", e)

    return result