from hypothesis import assume, given, strategies as st
from hypothesis.strategies import floats, lists, tuples
from src.core.engine.reliability_dynamics import (
    update_axis_structural, update_axis_performance, update_axis_context,
    update_axis_regulatory, update_axis_temporal, compute_reliability_vector
)

valid_axis_value = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
valid_drift = floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)
positive_days = floats(min_value=0.0, max_value=365*10, allow_nan=False, allow_infinity=False)
positive_alpha = floats(min_value=1e-6, max_value=1.0, allow_nan=False, allow_infinity=False)

class TestAxisInvariants:
    @given(valid_axis_value)
    def test_structural_stays_in_range(self, val):
        assert 0.0 <= update_axis_structural(val, []) <= 1.0
        assert 0.0 <= update_axis_structural(val, ["breaking_change"]) <= 1.0

    @given(valid_axis_value, valid_drift)
    def test_performance_stays_in_range(self, val, drift):
        assert 0.0 <= update_axis_performance(val, drift) <= 1.0

    @given(valid_axis_value, lists(st.dictionaries(keys=st.just("magnitude"), values=floats(0,1), min_size=1, max_size=5)))
    def test_context_stays_in_range(self, val, signals):
        assert 0.0 <= update_axis_context(val, signals) <= 1.0

    @given(valid_axis_value, lists(st.sampled_from(["major_change", "minor_change"]), max_size=3))
    def test_regulatory_stays_in_range(self, val, events):
        assert 0.0 <= update_axis_regulatory(val, events) <= 1.0

    @given(valid_axis_value, positive_days, positive_alpha)
    def test_temporal_stays_in_range(self, val, days, alpha):
        result = update_axis_temporal(val, days, alpha)
        assert 0.0 <= result <= 1.0

class TestTemporalMonotonicity:
    @given(positive_days, positive_alpha)
    def test_temporal_is_time_based_only(self, days, alpha):
        # The result should be independent of the stored value
        r1 = update_axis_temporal(1.0, days, alpha)
        r2 = update_axis_temporal(0.5, days, alpha)
        assert r1 == r2  # same elapsed_time -> same freshness

    @given(positive_days, positive_alpha)
    def test_longer_time_lower_value(self, days, alpha):
        assume(days > 1)
        r1 = update_axis_temporal(1.0, days, alpha)
        r2 = update_axis_temporal(1.0, days + 100, alpha)
        assert r2 <= r1 + 1e-6

class TestVectorCombination:
    @given(
        tuples(valid_axis_value, valid_axis_value, valid_axis_value, valid_axis_value, valid_axis_value),
        positive_days,
        positive_alpha,
    )
    def test_output_vector_is_valid(self, current_R, days, alpha):
        new_R = compute_reliability_vector(
            current_R=current_R, elapsed_days=days, alpha=alpha,
            structural_events=[], drift_metric=None, macro_signals=[], regulatory_events=[]
        )
        for val in new_R:
            assert 0.0 <= val <= 1.0

    @given(
        tuples(valid_axis_value, valid_axis_value, valid_axis_value, valid_axis_value, valid_axis_value),
        positive_days,
        positive_alpha,
        valid_drift,
    )
    def test_drift_only_affects_performance(self, current_R, days, alpha, drift):
        new_R = compute_reliability_vector(
            current_R=current_R, elapsed_days=days, alpha=alpha,
            structural_events=[], drift_metric=drift, macro_signals=[], regulatory_events=[]
        )
        if drift > 0:
            assert new_R[1] <= current_R[1] + 1e-6
