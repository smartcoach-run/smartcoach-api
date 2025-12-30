# adaptation_engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# --- Public contract ---------------------------------------------------------

PerceivedState = str  # "fatigued" | "neutral" | "good"


@dataclass(frozen=True)
class AdaptationOutcome:
    volume_factor: float          # e.g. 0.8
    intensity_cap: str            # e.g. "EF_ONLY" | "NO_ESCALATION" | "AS_PLANNED"
    target_type_override: Optional[str] = None  # e.g. "E" (optional)


def apply_adaptation(
    run_context: Dict[str, Any],
    base_decision: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Applies an explicit, bounded adaptation layer.

    Args:
      run_context: canonical context (Phase2 invariant). May contain adaptive_context (optional).
      base_decision: whatever SCN_2 computed before adaptation (must include enough to trace outcomes).

    Returns:
      adapted_decision: shallow copy of base_decision with explicit adaptation fields applied (if any).
      adaptation_trace: dict to be attached to decision_trace["adaptation"].
    """
    # --- Idempotence guard -----------------------------------------------
    # Prevent applying adaptation multiple times on the same slot/session
    if (run_context or {}).get("adaptation_applied") is True:
        adapted = dict(base_decision)
        adapted["adaptation"] = {
            "volume_factor": 1.0,
            "intensity_cap": "AS_PLANNED",
            "target_type_override": None,
        }

        adaptation_trace = {
            "inputs": {},
            "rules_applied": ["RG_ADP_990_ALREADY_APPLIED_SKIP"],
            "arbitrations": [],
            "safety_checks": ["SC_ADP_990_IDEMPOTENCE"],
            "outcome": adapted["adaptation"],
        }

        return adapted, adaptation_trace

    # Accept both legacy and SCN_2/SCN_6 contract
    adaptive_context = (
        (run_context or {}).get("adaptive_context")
        or (run_context or {}).get("adaptation")
        or {}
    )

    perceived_state: Optional[PerceivedState] = adaptive_context.get("perceived_state")


    # If no adaptive input => no-op (Phase 2 parity)
    if not perceived_state:
        return dict(base_decision), _trace_noop()

    rules_applied: List[str] = []
    arbitrations: List[str] = []
    safety_checks: List[str] = []

    # --- Default outcome (AS_PLANNED) ----------------------------------------
    outcome = AdaptationOutcome(
        volume_factor=1.0,
        intensity_cap="AS_PLANNED",
        target_type_override=None,
    )

    # --- Rules (V1) -----------------------------------------------------------
    if perceived_state == "fatigued":
        rules_applied.append("RG_ADP_001_FATIGUE_PROTECT")
        outcome = AdaptationOutcome(
            volume_factor=0.80,              # -20%
            intensity_cap="EF_ONLY",         # block I/T/VMA
            target_type_override="E",        # optional, if your decision uses codes
        )

    elif perceived_state == "neutral":
        rules_applied.append("RG_ADP_010_NEUTRAL_STABILITY")
        outcome = AdaptationOutcome(
            volume_factor=1.0,
            intensity_cap="NO_ESCALATION",   # keep planned, forbid increases
            target_type_override=None,
        )

    elif perceived_state == "good":
        rules_applied.append("RG_ADP_020_GOOD_FORM_CAP")
        # Micro-optimisation allowed but bounded
        outcome = AdaptationOutcome(
            volume_factor=1.05,              # +5% max (if engine chooses to apply)
            intensity_cap="NO_TYPE_UPSHIFT", # forbid changing E -> I, etc.
            target_type_override=None,
        )

    else:
        # Unknown value => ignore for safety, but trace it
        rules_applied.append("RG_ADP_900_UNKNOWN_STATE_IGNORED")
        outcome = AdaptationOutcome(
            volume_factor=1.0,
            intensity_cap="AS_PLANNED",
            target_type_override=None,
        )

    # --- Safety checks (V1) ---------------------------------------------------
    safety_checks.extend([
        "SC_ADP_001_NO_CHAIN_ESCALATION",
        "SC_ADP_002_ADAPTATION_CAP",
    ])

    # Enforce caps, regardless of rule outcome
    volume_factor = _cap(outcome.volume_factor, 0.70, 1.05)  # [-30%, +5%]
    intensity_cap = outcome.intensity_cap
    target_type_override = outcome.target_type_override

    adapted = dict(base_decision)
    adapted["adaptation"] = {
        "volume_factor": volume_factor,
        "intensity_cap": intensity_cap,
        "target_type_override": target_type_override,
    }

    adaptation_trace = {
        "inputs": {"perceived_state": perceived_state},
        "rules_applied": rules_applied,
        "arbitrations": arbitrations,
        "safety_checks": safety_checks,
        "outcome": {
            "volume_factor": volume_factor,
            "intensity_cap": intensity_cap,
            "target_type_override": target_type_override,
        },
    }
    # Mark adaptation as applied (idempotence)
    run_context["adaptation_applied"] = True

    return adapted, adaptation_trace



# --- Internals ---------------------------------------------------------------

def _cap(v: float, vmin: float, vmax: float) -> float:
    return max(vmin, min(vmax, v))


def _trace_noop() -> Dict[str, Any]:
    return {
        "inputs": {},
        "rules_applied": [],
        "arbitrations": [],
        "safety_checks": [],
        "outcome": {"volume_factor": 1.0, "intensity_cap": "AS_PLANNED", "target_type_override": None},
    }
