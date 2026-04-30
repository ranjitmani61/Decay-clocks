"""Nonlinear hazard aggregation – configurable gating and penalty modes."""
from __future__ import annotations
from typing import Dict, Tuple
from src.core.orchestrator.hazard import GovernanceAction


def compute_governance_action_nonlinear(
    reliability: Tuple[float, float, float, float, float],
    cost_config: Dict,
) -> Tuple[GovernanceAction, float]:
    """Return (action, hazard) using configurable aggregation mode.

    Supported modes (set in cost_config["hazard_mode"]):
        - "linear"     – weighted average (same as original)
        - "max"        – worst‑case dominates
        - "quadratic"  – squared penalty for severe drops
        - "hard_gate"  – immediate escalation if a dominant axis crosses a gate
    """
    weights = cost_config["weights"]
    C_err = cost_config["C_err"]
    C_int = cost_config["C_int"]
    provisional_hazard = cost_config["provisional_hazard"]
    floor_axes = cost_config.get("floor_axes", {})
    mode = cost_config.get("hazard_mode", "linear")
    dominant_axes = cost_config.get("dominant_axes", [])

    r_s, r_p, r_c, r_r, r_t = reliability

    # 1. Absolute floor check
    axis_map = {"s": r_s, "p": r_p, "c": r_c, "r": r_r, "t": r_t}
    for axis_key, floor_val in floor_axes.items():
        if axis_map.get(axis_key, 1.0) < floor_val:
            return (GovernanceAction.ESCALATE, 1.0)

    # 2. Degradations
    degradations = {
        "s": max(0.0, 1.0 - r_s),
        "p": max(0.0, 1.0 - r_p),
        "c": max(0.0, 1.0 - r_c),
        "r": max(0.0, 1.0 - r_r),
        "t": max(0.0, 1.0 - r_t),
    }

    # 3. Hard gate
    for axis_info in dominant_axes:
        axis = axis_info["axis"]
        gate = axis_info.get("gate_threshold", 0.3)
        if degradations.get(axis, 0.0) > gate:
            return (GovernanceAction.ESCALATE, 1.0)

    # 4. Aggregated hazard
    if mode == "max":
        hazard = max(weights.get(a, 0.0) * degradations[a] for a in degradations)
    elif mode == "quadratic":
        hazard = sum(
            weights.get(a, 0.0) * (degradations[a] ** 2) for a in degradations
        )
    else:  # linear (default)
        hazard = sum(weights.get(a, 0.0) * degradations[a] for a in degradations)

    hazard = max(0.0, min(1.0, hazard))

    # 5. Cost‑based decision
    expected_loss = hazard * C_err
    if expected_loss > C_int:
        return (GovernanceAction.ESCALATE, hazard)
    if hazard >= provisional_hazard:
        return (GovernanceAction.PROVISIONAL, hazard)
    return (GovernanceAction.ACTIVE, hazard)
