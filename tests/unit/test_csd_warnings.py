"""Tests for the complete CSD early‑warning function."""
from src.core.engine.csd import compute_csd_warnings


class TestComputeCSDWarnings:
    def test_no_warning_for_short_history(self):
        history = {"R_r": [1.0, 0.9, 0.8]}  # only 3 points, below min_window
        result = compute_csd_warnings(history, min_window=5)
        assert result["R_r"] is None

    def test_stable_axis_no_warning(self):
        history = {"R_t": [0.5] * 30}
        result = compute_csd_warnings(history, var_threshold=0.01)
        assert result["R_t"] is None

    def test_declining_trend_triggers_warning(self):
        # Linearly declining values → high variance + high autocorr
        values = [1.0 - i * 0.01 for i in range(30)]
        result = compute_csd_warnings({"R_p": values}, var_threshold=0.001, ac_threshold=0.3)
        assert result["R_p"] is not None
        assert "Critical slowing down detected" in result["R_p"]

    def test_multiple_axes_mixed(self):
        history = {
            "R_r": [1.0] * 30,  # stable
            "R_s": [1.0 - i * 0.01 for i in range(30)],  # declining
        }
        result = compute_csd_warnings(history, var_threshold=0.001, ac_threshold=0.3)
        assert result["R_r"] is None
        assert result["R_s"] is not None

    def test_custom_thresholds_respected(self):
        values = [1.0 - i * 0.005 for i in range(30)]  # slow decline
        result = compute_csd_warnings({"R_c": values}, var_threshold=0.1, ac_threshold=0.9)
        # Very high thresholds – should not trigger
        assert result["R_c"] is None
