# api.py

import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException

from pydantic import BaseModel

from core.config import config               # ← nouvelle config centralisée
from core.context import SmartCoachContext
from core.utils.logger import get_logger

from ics.router import router as ics_router
from ics.ics_builder import build_ics

from routes.selftest import router as selftest_router
from routes.resolve_slot import router as resolve_slot_router

from qa.registry_scn_6 import QA_SCN_6
from scenarios.dispatcher import dispatch_scenario
from scenarios.agregateur.scn_6 import run_scn_6
from scenarios.socle.scn_0g import run_scn_0g
from scenarios.socle.scn_0h import run_scn_0h

from tests.utils.snapshot import assert_snapshot
from tests.utils.helpers  import load_json

app = FastAPI()

app.include_router(ics_router)
app.include_router(selftest_router)
app.include_router(resolve_slot_router)

logger = logging.getLogger("API")

# =====================================================
#      MODELES DE REQUÊTES
# =====================================================

class GenerateRequest(BaseModel):
    scenario: str
    record_id: str
    payload: dict | None = None

class GenerateSessionRequest(BaseModel):
    """
    Requête minimale pour SCN_0g (Step6 OnDemand).
    Alignée avec SCN_0g V1.
    """
    slot: Dict[str, Any]

    # Champs optionnels pour compatibilité future
    scenario: Optional[str] = None
    record_id: Optional[str] = None

# =====================================================
#      HEALTH CHECK
# =====================================================

@app.get("/health")
def health():
    return {
        "status": "ok" if config.valid else "error",
        "environment": config.env,
        "running_in_fly": config.running_in_fly,
        "airtable_config_ok": config.valid,
    }

# =====================================================
#      ROUTE PRINCIPALE : /generate_by_id
# =====================================================

@app.post("/generate_by_id")
async def generate(body: GenerateRequest):
    logger.info(f"API → /generate_by_id called scenario={body.scenario}")

    scenario = body.scenario
    record_id = body.record_id
    internal_payload = body.payload or {}   # contient mode + run_context

    return dispatch_scenario(scenario, record_id, internal_payload)

# =====================================================
#      ROUTE SPÉCIALE : /generate_sessions
# =====================================================

@app.post("/generate_session")
async def generate_session(body: GenerateSessionRequest):
    """
    Endpoint technique Step6-OnDemand.
    Appelle directement le SOCLE SCN_0g.
    """
    logger.info("API → generate_session (SOCLE SCN_0g)")

    try:
        context = SmartCoachContext(
            scenario="SCN_0g",
            record_id=body.record_id,
            payload={
                "slot": body.slot
            }
        )

        result = run_scn_0g(context)

        return {
            "status": "ok",
            "message": "SCN_0g exécuté avec succès",
            "data": result
        }

    except Exception as e:
        logger.exception(f"Erreur dans generate_session : {e}")
        return {
            "success": False,
            "status": "error",
            "message": f"Erreur API : {e}",
            "source": "API",
            "data": None,
            "context": None
        }
# =====================================================
#      ROUTE DEBUG SOCLE : /socle/scn_0h_exec
# =====================================================

class PersistSlotRequest(BaseModel):
    slot: Dict[str, Any]
    record_id: str

@app.post("/socle/scn_0h_exec")
async def socle_scn_0h_exec(body: PersistSlotRequest):
    """
    Route TECHNIQUE de debug local pour SCN_0h.
    ❌ Jamais appelée par Make
    """
    logger.info("API → socle/scn_0h_exec (DEBUG SOCLE)")

    try:
        context = SmartCoachContext(
            scenario="SCN_0h",
            record_id=body.record_id,
            payload={}
        )

        result = run_scn_0h(
            context=context,
            slot=body.slot
        )

        return {
            "status": "ok",
            "message": "SCN_0h exécuté avec succès",
            "data": result
        }

    except Exception as e:
        logger.exception(f"Erreur SCN_0h : {e}")
        raise HTTPException(status_code=500, detail=str(e))
# =========================
# QA ENDPOINTS
# =========================
@app.get("/qa/run/scn_6")
def run_qa_scn_6():
    logger.info("[QA][SCN_6] Lancement de la suite QA")

    results = []

    logger.info(f"[QA][SCN_6] {len(QA_SCN_6)} test(s) détecté(s)")

    for test in QA_SCN_6:
        test_id = test.get("test_id", "UNKNOWN_TEST")

        try:
            logger.info(f"[QA][SCN_6] ▶️ Test {test_id}")

            input_json = load_json(test["input_file"])

            result = run_scn_6(
                payload=input_json["payload"],
                record_id=input_json.get("record_id")
            )

            if not result.success:
                raise AssertionError(result.message)

            assert_snapshot(
                actual=result.data,
                expected_file=test["expected_file"]
            )

            results.append({
                "test_id": test_id,
                "status": "PASSED"
            })

            logger.info(f"[QA][SCN_6] ✅ Test {test_id} PASSED")

        except Exception as e:
            logger.error(f"[QA][SCN_6] ❌ Test {test_id} FAILED : {e}")

            results.append({
                "test_id": test_id,
                "status": "FAILED",
                "error": str(e)
            })

    passed = len([r for r in results if r["status"] == "PASSED"])
    failed = len([r for r in results if r["status"] == "FAILED"])

    return {
        "success": failed == 0,
        "suite": "SCN_6",
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed
        },
        "results": results
    }

