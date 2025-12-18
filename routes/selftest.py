# selftest.py
from fastapi import APIRouter, HTTPException
from scenarios.agregateur.scn_6 import run_scn_6

router = APIRouter(prefix="/selftest", tags=["selftest"])

def build_diagnostic(
    *,
    expected_scenario: str,
    actual_scenario: str,
    expected_family: str,
    actual_family: str,
    expected_duration: int,
    actual_duration: int,
    strict: bool = True,
):
    causes = []

    causes.append({
        "rule": "SCENARIO_MATCH",
        "expected": expected_scenario,
        "actual": actual_scenario,
        "status": "OK" if expected_scenario == actual_scenario else "FAILED",
    })

    causes.append({
        "rule": "MODEL_FAMILY_MATCH",
        "expected": expected_family,
        "actual": actual_family,
        "status": "OK" if expected_family == actual_family else "FAILED",
    })

    causes.append({
        "rule": "DURATION_MATCH",
        "expected": expected_duration,
        "actual": actual_duration,
        "status": "OK" if expected_duration == actual_duration else "FAILED",
    })

    has_failure = any(c["status"] == "FAILED" for c in causes)

    if strict:
        causes.append({
            "rule": "STRICT_CONFORMITY",
            "expected": True,
            "actual": not has_failure,
            "status": "FAILED" if has_failure else "OK",
            "detail": "Mode strict : toute divergence invalide le self-test"
        })

    summary = "FAILED" if any(c["status"] == "FAILED" for c in causes) else "OK"
    main_cause = next((c["rule"] for c in causes if c["status"] == "FAILED"), None)

    return {"summary": summary, "main_cause": main_cause, "causes": causes}

def format_war_room_summary(war_room: dict) -> dict:
    inputs = war_room.get("inputs", {})

    return {
        "Contexte": {
            "Mode": inputs.get("mode"),
            "Sous-mode": inputs.get("submode"),
            "Objectif": inputs.get("objective_type"),
            "Chrono cible": inputs.get("objective_time"),
            "Âge": inputs.get("age"),
        },
        "Décision moteur": {
            "Scénario retenu": war_room.get("scenario_id"),
            "Famille de séance": war_room.get("model_family"),
            "Score": war_room.get("scores", {}).get(
                war_room.get("scenario_id")
            ),
        }
    }


@router.get("/scn_001")
def selftest_scn_001():
    """
    Self-test SC-001 :
    Homme 45 ans, Marathon, Reprise, 3h45, séance Q1.
    Vérifie que SCN_6 + SC-001 + SCN_0g renvoient
    bien la famille MARA_REPRISE_Q1 et une durée de 54'.
    """

    payload = {
        "mode": "ondemand",
        "run_context": {
            "profile": {
                "age": 45,
                "genre": "Homme",
                "vdot": 51
            },
            "objectif": {
                "discipline": "Running",
                "type": "Marathon",
                "experience": "Reprise",
                "chrono_cible": "03:45:00"
            },
            "slot": {
                "slot_id": "selftest_slot_sc001",
                "date": "2025-12-11",
                "phase": "Reprise",
                "type": "Q1"
            },
            "historique": []
        }
    }

    result = run_scn_6(payload=payload, record_id="selftest_rec001")

    if not result.success:
        # SCN_6 a échoué → 500 direct
        raise HTTPException(
            status_code=500,
            detail={
                "error": result.message,
                "war_room": result.data.get("war_room", {})
            },
        )

    data = result.data or {}
    session = data.get("session", {})
    metadata = session.get("metadata", {})

    family = metadata.get("family")
    duration = session.get("duration_total")
    war_room = data.get("war_room", {})
       
    diagnostic = build_diagnostic(
        expected_scenario="SC-001",
        actual_scenario=war_room.get("scenario_id"),
        expected_family="MARA_REPRISE_Q1",
        expected_duration=54,
        actual_family=family,
        actual_duration=duration,
        strict=True,
    )
    war_room_summary = format_war_room_summary(war_room)

    # Tout est OK
    return {
        "status": "ok" if diagnostic["summary"] == "OK" else "error",
        "message": "SC-001 OK" if diagnostic["summary"] == "OK" else "SC-001 FAILED",

        # Données brutes moteur (utile pour debug avancé)
        "data": data,

        # Diagnostic structuré (utilisé par Make)
        "diagnostic": diagnostic,

        # Synthèse lisible du war_room (pour mail / alertes)
        "war_room_summary": war_room_summary,
    }
