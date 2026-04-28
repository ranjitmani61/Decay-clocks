"""Unit tests for configuration validation."""
from src.core.orchestrator.config_validator import (
    validate_cost_config,
    validate_debounce_config,
)

class TestValidateCostConfig:
    def test_valid_config(self):
        valid = {
            "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
            "C_err": 500.0,
            "C_int": 100.0,
            "provisional_hazard": 0.3,
            "floor_axes": {"r": 0.3, "s": 0.15},
        }
        assert validate_cost_config(valid) == []

    def test_missing_weights_key(self):
        config = {
            "C_err": 500.0,
            "C_int": 100.0,
            "provisional_hazard": 0.3,
            "floor_axes": {},
        }
        errors = validate_cost_config(config)
        assert any("weights" in e for e in errors)

    def test_weights_not_sum_to_one(self):
        config = {
            "weights": {"s": 0.6, "p": 0.5},  # sum = 1.1
            "C_err": 500,
            "C_int": 100,
            "provisional_hazard": 0.3,
            "floor_axes": {},
        }
        errors = validate_cost_config(config)
        assert any("sum" in e.lower() for e in errors)

    def test_weights_negative(self):
        config = {
            "weights": {"s": -0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.6},
            "C_err": 500,
            "C_int": 100,
            "provisional_hazard": 0.3,
            "floor_axes": {},
        }
        errors = validate_cost_config(config)
        assert any("negative" in e.lower() for e in errors)

    def test_negative_cost(self):
        config = {
            "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
            "C_err": -10,
            "C_int": 100,
            "provisional_hazard": 0.3,
            "floor_axes": {},
        }
        errors = validate_cost_config(config)
        assert any("C_err" in e for e in errors)

    def test_provisional_hazard_out_of_range(self):
        config = {
            "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
            "C_err": 500,
            "C_int": 100,
            "provisional_hazard": 1.5,
            "floor_axes": {},
        }
        errors = validate_cost_config(config)
        assert any("provisional_hazard" in e for e in errors)

    def test_floor_axes_bad_key(self):
        config = {
            "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
            "C_err": 500,
            "C_int": 100,
            "provisional_hazard": 0.3,
            "floor_axes": {"invalid_axis": 0.5},
        }
        errors = validate_cost_config(config)
        assert any("invalid axis" in e.lower() for e in errors)

    def test_floor_axes_value_out_of_range(self):
        config = {
            "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
            "C_err": 500,
            "C_int": 100,
            "provisional_hazard": 0.3,
            "floor_axes": {"r": 1.2},
        }
        errors = validate_cost_config(config)
        assert any("floor" in e.lower() for e in errors)


class TestValidateDebounceConfig:
    def test_valid(self):
        cfg = {"regulatory": 24, "macroeconomic": 24, "structural": 0}
        assert validate_debounce_config(cfg) == []

    def test_unknown_signal_type(self):
        cfg = {"invalid_type": 10}
        errors = validate_debounce_config(cfg)
        assert any("unknown" in e.lower() for e in errors)

    def test_negative_hours(self):
        cfg = {"regulatory": -5}
        errors = validate_debounce_config(cfg)
        assert any("negative" in e.lower() for e in errors)
