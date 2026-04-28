"""Cost‑informed governance action derived from the reliability vector.

Returns a discrete action (ACTIVE, PROVISIONAL, ESCALATE) and a continuous hazard score.
"""
from __future__ import annotations
from enum import Enum
from typing import Dict, Tuple

class GovernanceAction(str, Enum):
    ACTIVE = "ACTIVE"
    PROVISIONAL = "PROVISIONAL"
    ESCALATE = "ESCALATE"

# ── public API ────────────────────────────────────────

def compute_governance_action(
    reliability: Tuple[float, float, float, float, float],
    config: dict,
) -> Tuple[GovernanceAction, float]:
    """Decide governance action based on reliability vector and cost model.

    Args:
        reliability: (r_s, r_p, r_c, r_r, r_t)
        config: dictionary with:
            - weights: dict of axis weights (s, p, c, r, t) summing to 1.0
            - C_err: cost of an erroneous decision (float)
            - C_int: cost of a human review intervention (float)
            - provisional_hazard: hazard score above which output becomes provisional (float)
            - floor_axes: dict mapping axis key to minimum allowed value before forced escalation

    Returns:
        (action, hazard_score)
    """
    weights = config["weights"]
    C_err = float(config["C_err"])
    C_int = float(config["C_int"])
    prov_thresh = float(config["provisional_hazard"])
    floors = config.get("floor_axes", {})

    r_s, r_p, r_c, r_r, r_t = reliability

    # Weighted risk = sum( w_i * (1 - r_i) )   in [0,1]
    hazard = (
        weights.get("s", 0.0) * (1.0 - r_s) +
        weights.get("p", 0.0) * (1.0 - r_p) +
        weights.get("c", 0.0) * (1.0 - r_c) +
        weights.get("r", 0.0) * (1.0 - r_r) +
        weights.get("t", 0.0) * (1.0 - r_t)
    )
    hazard = max(0.0, min(1.0, hazard))

    # Check absolute axis floors (force escalate)
    axis_lookup = {"s": r_s, "p": r_p, "c": r_c, "r": r_r, "t": r_t}
    for axis_key, floor_val in floors.items():
        if axis_lookup.get(axis_key, 1.0) < floor_val:
            return (GovernanceAction.ESCALATE, hazard)

    # Cost‑based decision
    expected_loss = hazard * C_err
    if expected_loss > C_int:
        return (GovernanceAction.ESCALATE, hazard)

    if hazard >= prov_thresh:
        return (GovernanceAction.PROVISIONAL, hazard)

    return (GovernanceAction.ACTIVE, hazard)
