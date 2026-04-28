"""Test the Bayesian calibration engine."""
import math
import pytest
from src.core.engine.calibration import (
    update_signal_quality,
    update_half_life,
    adjust_threshold,
)

class TestUpdateSignalQuality:
    def test_perfect_accuracy_increases_quality(self):
        # Start with alpha=1, beta=1 (uniform prior)
        prior = (1, 1)  # beta(1,1) -> mean 0.5
        new_alpha, new_beta = update_signal_quality(
            alpha=prior[0], beta=prior[1], review_outcome=True
        )
        # After one success, mean = (alpha+1)/(alpha+beta+1) = 2/3 ≈ 0.666
        assert new_alpha == 2
        assert new_beta == 1

    def test_failure_decreases_quality(self):
        prior = (10, 2)  # mean 10/12 ≈ 0.833
        new_alpha, new_beta = update_signal_quality(
            alpha=prior[0], beta=prior[1], review_outcome=False
        )
        # After failure, alpha unchanged, beta+1
        assert new_alpha == 10
        assert new_beta == 3
        # mean becomes 10/13 ≈ 0.769

    def test_quality_does_not_explode(self):
        # After many updates, values remain finite
        a, b = 1000, 5
        for _ in range(100):
            a, b = update_signal_quality(a, b, True)
        assert a > 1000
        assert a < 2000  # reasonable range

    def test_input_validation_raises(self):
        with pytest.raises(ValueError):
            update_signal_quality(-1, 1, True)


class TestUpdateHalfLife:
    def test_stale_before_predictive_shrinks_half_life(self):
        # Expected half life = 100 days; node found stale at 60 days
        new_hl = update_half_life(current_half_life=100.0,
                                  elapsed_days_since_valid=60.0,
                                  node_was_stale=True,
                                  c_t_at_review=0.7)
        # Should decrease because node was stale earlier than expected
        assert new_hl < 100.0

    def test_valid_beyond_predicted_lengthens_half_life(self):
        # Node still valid at 150 days, c(t)=0.9
        new_hl = update_half_life(current_half_life=100.0,
                                  elapsed_days_since_valid=150.0,
                                  node_was_stale=False,
                                  c_t_at_review=0.9)
        assert new_hl > 100.0

    def test_floor_and_ceiling(self):
        # Already very short half life
        hl = 10.0
        hl = update_half_life(hl, 5.0, True, 0.6)
        assert hl >= 5.0  # never below 5
        # Very long half life
        hl = 10000.0
        hl = update_half_life(hl, 5000.0, False, 0.8)
        assert hl <= 365 * 5  # capped at ~5 years

    def test_no_change_on_equal(self):
        # Node exactly at half life, stale -> no change (or minimal)
        hl = 100.0
        hl2 = update_half_life(hl, 100.0, True, 0.5)
        assert hl2 == pytest.approx(hl, abs=5)


class TestAdjustThreshold:
    def test_high_false_positive_lowers(self):
        # current provisional threshold 0.6, false positive rate 0.5 -> reduce
        new_t = adjust_threshold(current_threshold=0.6,
                                 false_positive_rate=0.5,
                                 desired_fpr=0.1)
        assert new_t < 0.6

    def test_low_fpr_increases(self):
        new_t = adjust_threshold(current_threshold=0.3,
                                 false_positive_rate=0.02,
                                 desired_fpr=0.1)
        assert new_t > 0.3

    def test_clamped_to_range(self):
        # Very low threshold
        t = adjust_threshold(0.05, 0.0, 0.1)
        assert t >= 0.01
        # Very high
        t2 = adjust_threshold(0.95, 0.5, 0.1)
        assert t2 <= 0.99
