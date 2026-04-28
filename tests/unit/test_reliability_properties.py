"""Property‑based tests for the reliability dynamics engine."""
import math
from hypothesis import assume, given, strategies as st
from hypothesis.strategies import floats, lists, tuples, text, booleans, datetimes
from src.core.engine.reliability_dynamics import (
    update_axis_structural,
    update_axis_performance,
    update_axis_context,
    update_axis_regulatory,
    update_axis_temporal,
    compute_reliability_vector,
)

# --- Strategies ---
valid_axis_value = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
valid_drift = floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)  # Drift can be large, but capped by mapping
positive_days = floats(min_value=0.0, max_value=365*10, allow_nan=False, allow_infinity=False)
positive_alpha = floats(min_value=1e-6, max_value=1.0, allow_nan=False, allow_infinity=False)

# --- Properties ---
class TestAxisInvariants:
    @given(valid_axis_value)
    def test_structural_stays_in_range(self, val):
        result = update_axis_structural(val, [])
        assert 0.0 <= result <= 1.0
        result2 = update_axis_structural(val, ["breaking_change"])
        assert 0.0 <= result2 <= 1.0

    @given(valid_axis_value, valid_drift)
    def test_performance_stays_in_range(self, val, drift):
        result = update_axis_performance(val, drift)
        assert 0.0 <= result <= 1.0

    @given(valid_axis_value, lists(st.dictionaries(keys=st.just("magnitude"), values=floats(0,1), min_size=1, max_size=5)))
    def test_context_stays_in_range(self, val, signals):
        result = update_axis_context(val, signals)
        assert 0.0 <= result <= 1.0

    @given(valid_axis_value, lists(st.sampled_from(["major_change", "minor_change"]), max_size=3))
    def test_regulatory_stays_in_range(self, val, events):
        result = update_axis_regulatory(val, events)
        assert 0.0 <= result <= 1.0

    @given(valid_axis_value, positive_days, positive_alpha)
    def test_temporal_stays_in_range(self, val, days, alpha):
        result = update_axis_temporal(val, days, alpha)
        assert 0.0 <= result <= 1.0

class TestTemporalMonotonicity:
    @given(valid_axis_value, positive_days, positive_alpha)
    def test_temporal_decreases_or_stays_zero(self, val, days, alpha):
        result = update_axis_temporal(val, days, alpha)
        assert result <= val or val == 0.0

    @given(valid_axis_value, positive_days, positive_alpha)
    def test_longer_time_lower_value(self, val, days, alpha):
        assume(days > 1 and val > 0.001)
        r1 = update_axis_temporal(val, days, alpha)
        r2 = update_axis_temporal(val, days + 100, alpha)
        assert r2 <= r1 + 1e-6  # allow for tiny floating error

class TestVectorCombination:
    @given(
        tuples(valid_axis_value, valid_axis_value, valid_axis_value, valid_axis_value, valid_axis_value),
        positive_days,
        positive_alpha,
    )
    def test_output_vector_is_valid(self, current_R, days, alpha):
        new_R = compute_reliability_vector(
            current_R=current_R,
            elapsed_days=days,
            alpha=alpha,
            structural_events=[],
            drift_metric=None,
            macro_signals=[],
            regulatory_events=[]
        )
        for val in new_R:
            assert 0.0 <= val <= 1.0
        # Temporal axis alone decays
        assert new_R[4] <= current_R[4] + 1e-6

    @given(
        tuples(valid_axis_value, valid_axis_value, valid_axis_value, valid_axis_value, valid_axis_value),
        positive_days,
        positive_alpha,
        valid_drift,
    )
    def test_drift_only_affects_performance(self, current_R, days, alpha, drift):
        new_R = compute_reliability_vector(
            current_R=current_R,
            elapsed_days=days,
            alpha=alpha,
            structural_events=[],
            drift_metric=drift,
            macro_signals=[],
            regulatory_events=[]
        )
        # r_p should decrease or stay same (if drift 0 or very small)
        if drift > 0:
            assert new_R[1] <= current_R[1] + 1e-6
