"""Tests for the CSD early‑warning mathematical functions."""
import math
import pytest
from src.core.engine.csd import rolling_variance, lag1_autocorr


class TestRollingVariance:
    def test_constant_series_zero(self):
        assert rolling_variance([0.5, 0.5, 0.5, 0.5]) == 0.0

    def test_small_set(self):
        vals = [1.0, 0.8, 0.6, 0.4, 0.2]
        expected = 0.08
        assert rolling_variance(vals) == pytest.approx(expected)

    def test_single_value_zero(self):
        assert rolling_variance([42.0]) == 0.0

    def test_empty_zero(self):
        assert rolling_variance([]) == 0.0


class TestLag1Autocorr:
    def test_perfect_positive(self):
        vals = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        assert lag1_autocorr(vals) > 0.9

    def test_low_correlation(self):
        # A sequence with no strong structure should be weakly correlated
        vals = [0.5, 0.2, 0.9, 0.1, 0.4, 0.8]
        result = lag1_autocorr(vals)
        assert -0.7 <= result <= 0.7

    def test_alternating_negative(self):
        vals = [1.0, 0.0, 1.0, 0.0, 1.0]
        assert lag1_autocorr(vals) < -0.5

    def test_short_series_zero(self):
        assert lag1_autocorr([1.0, 2.0]) == 0.0
