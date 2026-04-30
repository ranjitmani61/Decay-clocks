import pytest
from src.core.orchestrator.hazard import compute_governance_action, GovernanceAction

# Default config for testing: all axes weight 0.2, thresholds
DEFAULT_CONFIG = {
    "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
    "C_err": 1000.0,          # cost of an incorrect decision
    "C_int": 100.0,           # cost of intervention (review)
    "provisional_hazard": 0.3,
    "floor_axes": {"r": 0.3, "s": 0.15}  # force escalate if any axis below floor
}

class TestComputeGovernanceAction:
    def test_perfect_reliability_is_active(self):
        R = (1.0, 1.0, 1.0, 1.0, 1.0)
        status, hazard, reason = compute_governance_action(R, DEFAULT_CONFIG)
        assert status == GovernanceAction.ACTIVE
        assert hazard == pytest.approx(0.0)

    def test_moderate_degradation_provisional(self):
        # all axes 0.6 => risk = 0.4 each, weighted sum = 0.4, hazard=0.4
        R = (0.6, 0.6, 0.6, 0.6, 0.6)
        status, hazard, _ = compute_governance_action(R, DEFAULT_CONFIG)
        # hazard = 0.4 > 0.3 provisional threshold, but cost check: 0.4*1000=400 > 100 => also would escalate
        # But we want provisional only if hazard between 0.3 and where cost says escalate.
        # Let's adjust config to avoid automatic escalation.
        config = {**DEFAULT_CONFIG, "C_err": 200.0}  # cost 200, intervention 100 => escalate if hazard>0.5
        R = (0.7, 0.7, 0.7, 0.7, 0.7)  # hazard=0.3 -> cost=60 < 100 => no escalate, provisional
        status, hazard, _ = compute_governance_action(R, config)
        assert status == GovernanceAction.PROVISIONAL
        assert hazard == pytest.approx(0.3)

    def test_high_risk_escalates(self):
        R = (0.2, 0.9, 0.9, 0.9, 0.9)  # structural axis very low
        status, hazard, _ = compute_governance_action(R, DEFAULT_CONFIG)
        # Weighted risk = 0.2*0.8 = 0.16 -> hazard 0.16 which might not escalate by cost
        # But structural floor 0.15 not breached. So won't escalate by floor.
        # Need a case that crosses cost threshold: make error cost low enough to escalate.
        config = {**DEFAULT_CONFIG, "C_err": 200.0, "C_int": 10.0}
        R = (0.3, 1.0, 1.0, 1.0, 1.0)  # weighted hazard = 0.2*0.7 = 0.14, cost=28 > 10 => escalate
        status, hazard, _ = compute_governance_action(R, config)
        assert status == GovernanceAction.ESCALATE

    def test_axis_floor_forces_escalate(self):
        # regulatory floor = 0.3; we set r_r = 0.2
        R = (1.0, 1.0, 1.0, 0.2, 1.0)
        status, hazard, _ = compute_governance_action(R, DEFAULT_CONFIG)
        assert status == GovernanceAction.ESCALATE

    def test_structural_floor_forces_escalate(self):
        R = (0.14, 1.0, 1.0, 1.0, 1.0)
        status, _, _ = compute_governance_action(R, DEFAULT_CONFIG)
        assert status == GovernanceAction.ESCALATE

    def test_zero_hazard_when_all_axes_one(self):
        R = (1.0, 1.0, 1.0, 1.0, 1.0)
        _, hazard, _ = compute_governance_action(R, DEFAULT_CONFIG)
        assert hazard == 0.0
