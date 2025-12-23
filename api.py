# api.py
print("🔥 API VERSION = SLOT_GENERATOR_V1_LOADED")
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, APIRouter
from datetime import date

from pydantic import BaseModel

from core.config import config               # ← nouvelle config centralisée
from core.context import SmartCoachContext
from core.slot_payload import SlotPayload
from core.utils.logger import get_logger
from infra.slot_resolution import router as core_1_router
from infra.slot_navigation import router as core_3_router

from ics.router import router as ics_router
from ics.ics_builder import build_ics

from render_message import router as render_message_router

from routes.selftest import router as selftest_router
from routes.resolve_slot import router as resolve_slot_router

from qa.registry_scn_6 import QA_SCN_6
from scenarios.dispatcher import dispatch_scenario
from scenarios.agregateur.scn_1_v2 import scn_1_v2_init_slots
from scenarios.agregateur.scn_6 import run_scn_6
from scenarios.socle.scn_0g import run_scn_0g
from scenarios.socle.scn_0h import run_scn_0h
from scenarios.agregateur.scn_slot_generator import run_scn_slot_generator as run_first
from scenarios.agregateur.scn_slot_resolver import run_scn_slot_resolver as run_next

from tests.utils.snapshot import assert_snapshot
from tests.utils.helpers  import load_json

app = FastAPI()
router = APIRouter(prefix="/core", tags=["CORE"])

app.include_router(router)
app.include_router(ics_router)
app.include_router(selftest_router)
app.include_router(core_1_router)
app.include_router(core_3_router)
app.include_router(resolve_slot_router)
app.include_router(render_message_router)

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


class CoreRunRequest(BaseModel):
    mode: str                      # NEXT | FIRST | FEEDBACK
    plan_id: Optional[str] = None  # temporaire (root context)
    options: Dict[str, Any] = {}

APP_VERSION = "2025-12-23-SCN6-OK"

@app.get("/version")
def get_version():
    return {
        "version": APP_VERSION
    }


@app.post("/resolve_slot")
def resolve_slot(payload: SlotPayload):

    if payload.mode == "FIRST":
        return run_first(payload)

    if payload.mode == "NEXT":
        return run_next(payload)

    return {
        "success": False,
        "status": "error",
        "message": f"Mode non implémenté: {payload.mode}",
        "source": "API"
    }

@router.post("/run")
def core_run(body: CoreRunRequest):
    """
    Point d’entrée runtime unique pour Make (CORE_2 V2).
    """
    try:
        # 1) Résolution du slot
        resolved = resolve_slot(
            plan_id=body.plan_id,
            mode=body.mode,
        )

        if not resolved.success:
            return resolved.to_dict()

        # 2) Préparation du run_context
        payload = {
            "run_context": {
                "slot": resolved.data["slot"],
                "profile": resolved.data.get("profile", {}),
                "objective": resolved.data.get("objective", {}),
                "objectif_normalisé": resolved.data.get("objectif_normalisé"),
            }
        }

        # 3) Orchestration SCN_6
        result = run_scn_6(
            payload=payload,
            record_id=body.plan_id,
        )

        return result.to_dict()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class Scn1V2Payload(BaseModel):
    plan_record_id: str
    user_id: str
    date_debut: date
    nb_semaines: int
    sessions_per_week: int
    dispos: List[str]


@router.post("/scn_1_v2/init_slots")
def init_slots(payload: Scn1V2Payload):
    return scn_1_v2_init_slots(
        plan_record_id=payload.plan_record_id,
        user_id=payload.user_id,
        date_debut=payload.date_debut,
        nb_semaines=payload.nb_semaines,
        sessions_per_week=payload.sessions_per_week,
        dispos=payload.dispos,
    )    
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

@app.get("/ping")
def ping():
    return {"status": "ok"}