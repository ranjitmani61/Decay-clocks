import math
import pytest
from src.core.engine.reliability_dynamics import (
    update_axis_structural, update_axis_performance, update_axis_context,
    update_axis_regulatory, update_axis_temporal, compute_reliability_vector
)

class TestStructuralValidity:
    def test_no_change(self):
        assert update_axis_structural(1.0, []) == 1.0
    def test_breaking_change(self):
        assert update_axis_structural(1.0, ["breaking_change"]) == 0.2

class TestPerformanceAxis:
    def test_no_drift(self):
        assert update_axis_performance(0.8, None) == pytest.approx(0.8)
    def test_penalty(self):
        val = update_axis_performance(1.0, 0.3, lambda d: min(1.0, d*2))
        assert val == pytest.approx(0.4)
    def test_floor(self):
        assert update_axis_performance(0.1, 1.0, lambda d: 1.0) == 0.0

class TestContextAlignment:
    def test_no_signals(self):
        assert update_axis_context(0.7, []) == pytest.approx(0.7)
    def test_single_shock(self):
        assert update_axis_context(1.0, [{"magnitude":0.3}]) == pytest.approx(0.7)
    def test_accumulate(self):
        sigs = [{"magnitude":0.2},{"magnitude":0.3}]
        assert update_axis_context(0.9, sigs) == pytest.approx(0.4)
    def test_floor(self):
        assert update_axis_context(0.3, [{"magnitude":1.5}]) == 0.0

class TestRegulatoryCompliance:
    def test_none(self):
        assert update_axis_regulatory(1.0, []) == 1.0
    def test_major(self):
        assert update_axis_regulatory(1.0, ["major_change"]) == 0.3
    def test_minor(self):
        assert update_axis_regulatory(0.9, ["minor_change"]) == pytest.approx(0.8)

class TestTemporalFreshness:
    def test_no_elapsed(self):
        assert update_axis_temporal(0.8, 0, 0.01) == pytest.approx(0.8)
    def test_half_life(self):
        alpha = 0.00693
        val = update_axis_temporal(1.0, 100, alpha)
        assert val == pytest.approx(0.5, abs=1e-3)
    def test_floor(self):
        # alpha=0.01, t=1000 => exp(-10) = 4.5e-5, times 0.1 = 4.5e-6 < 0.001 => floored to 0
        val = update_axis_temporal(0.1, 1000, 0.01)
        assert val == 0.0

class TestComputeReliabilityVector:
    def test_no_signals(self):
        new_R = compute_reliability_vector(
            current_R=(1.0,1.0,1.0,1.0,1.0),
            elapsed_days=10,
            alpha=0.001,
            structural_events=[],
            drift_metric=None,
            macro_signals=[],
            regulatory_events=[]
        )
        expected_t = 1.0 * math.exp(-0.001 * 10)
        assert new_R[4] == pytest.approx(expected_t, abs=1e-4)
        assert new_R[:4] == (1.0,1.0,1.0,1.0)

    def test_multiple_axes(self):
        new_R = compute_reliability_vector(
            current_R=(0.8,0.9,0.7,0.6,0.5),
            elapsed_days=5,
            alpha=0.01,
            structural_events=["breaking_change"],
            drift_metric=0.5,
            macro_signals=[{"magnitude":0.2}],
            regulatory_events=["minor_change"]
        )
        assert new_R[0] == 0.2
        assert new_R[1] == pytest.approx(0.4)
        assert new_R[2] == pytest.approx(0.5)
        assert new_R[3] == pytest.approx(0.5)
        expected_t = 0.5 * math.exp(-0.01 * 5)
        assert new_R[4] == pytest.approx(expected_t, abs=1e-4)
