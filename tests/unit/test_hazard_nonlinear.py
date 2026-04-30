import pytest
from src.core.orchestrator.hazard_nonlinear import compute_governance_action_nonlinear
from src.core.orchestrator.hazard import GovernanceAction

BASE_CONFIG = {
    "weights": {"s":0.2, "p":0.2, "c":0.2, "r":0.2, "t":0.2},
    "C_err": 500, "C_int": 1000,
    "provisional_hazard": 0.2,
    "floor_axes": {"r":0.2, "s":0.1},
    "hazard_mode": "linear"
}

class TestLinearMode:
    def test_perfect_is_active(self):
        action, h = compute_governance_action_nonlinear((1,1,1,1,1), BASE_CONFIG)
        assert action == GovernanceAction.ACTIVE
        assert h == 0.0

    def test_regulatory_drop_provisional(self):
        config = {**BASE_CONFIG, "provisional_hazard": 0.1}
        action, h = compute_governance_action_nonlinear((1,1,1,0.3,1), config)
        assert action == GovernanceAction.PROVISIONAL
        assert h == pytest.approx(0.14)

class TestMaxMode:
    def test_max_only(self):
        # max mode: single bad axis dominates, but cost may still prevent escalation
        config = {**BASE_CONFIG, "hazard_mode": "max", "weights": {"s":1, "p":1, "c":1, "r":1, "t":1}}
        action, h = compute_governance_action_nonlinear((1,1,1,0.3,1), config)
        # hazard = 0.7, expected loss = 350 < C_int=1000 → PROVISIONAL
        assert action == GovernanceAction.PROVISIONAL
        assert h == pytest.approx(0.7)

class TestQuadraticMode:
    def test_quadratic_penalty(self):
        config = {**BASE_CONFIG, "hazard_mode": "quadratic", "provisional_hazard": 0.05}
        action, h = compute_governance_action_nonlinear((1,1,1,0.3,1), config)
        assert h == pytest.approx(0.098)
        assert action == GovernanceAction.PROVISIONAL

class TestHardGateMode:
    def test_gate_triggered(self):
        config = {**BASE_CONFIG, "hazard_mode": "linear",
                  "dominant_axes": [{"axis": "r", "gate_threshold": 0.5}]}
        action, h = compute_governance_action_nonlinear((1,1,1,0.3,1), config)
        assert action == GovernanceAction.ESCALATE
        assert h == 1.0

    def test_gate_not_triggered(self):
        config = {**BASE_CONFIG, "hazard_mode": "linear",
                  "dominant_axes": [{"axis": "r", "gate_threshold": 0.8}]}
        action, h = compute_governance_action_nonlinear((1,1,1,0.3,1), config)
        # Normal linear path; hazard=0.14 < 0.2 → ACTIVE
        assert action == GovernanceAction.ACTIVE
