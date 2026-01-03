# scenarios/core_simple.py

from typing import Dict, Any
from scenarios.dispatcher import SmartCoachContext
from scenarios.agregateur.adaptation_engine import compute_adaptation
from scenarios.agregateur.slot_generator import generate_slot_session


SCENARIO_ID = "CORE_SIMPLE_V1"
ENGINE_ID = "SLOT_GENERATOR_V1"


def run_core_simple(context: SmartCoachContext) -> Dict[str, Any]:
    """
    Génère une séance simple et robuste à partir du run_context.
    Aucun fallback. Aucune sélection dynamique.
    """

    payload = context.payload or {}

    run_ctx = payload.get("run_context")
    if not run_ctx:
        raise ValueError("run_context manquant")

    # 1️⃣ Adaptation (optionnelle)
    adaptation = compute_adaptation(run_ctx)

    # 2️⃣ Génération de la séance (moteur V1 maîtrisé)
    session = generate_slot_session(
        slot=run_ctx["slot"],
        profile=run_ctx["profile"],
        objective=run_ctx.get("objective"),
        adaptation=adaptation,
    )

    # 3️⃣ Meta minimale
    meta = {
        "scenario": SCENARIO_ID,
        "engine": ENGINE_ID,
        "adaptation_applied": adaptation is not None,
        "rules": adaptation.get("rules_applied", []) if adaptation else [],
    }

    return {
        "session": session,
        "meta": meta,
    }