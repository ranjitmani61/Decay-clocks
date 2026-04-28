"""Configuration validation for governance pipeline."""
from typing import Dict, List, Any

# Known axes and signal types
VALID_AXES = {"s", "p", "c", "r", "t"}
VALID_SIGNAL_TYPES = {"regulatory", "macroeconomic", "structural",
                      "behavioural", "performance"}

def validate_cost_config(config: Dict[str, Any]) -> List[str]:
    """Return list of error messages; empty if valid."""
    errors = []
    if "weights" not in config:
        errors.append("Missing 'weights' in cost_config")
        return errors  # can't check further

    weights = config["weights"]
    if not isinstance(weights, dict):
        errors.append("'weights' must be a dict")
        return errors

    for k, v in weights.items():
        if k not in VALID_AXES:
            errors.append(f"Invalid weight key '{k}'; must be one of {VALID_AXES}")
        elif not isinstance(v, (int, float)) or v < 0:
            errors.append(f"Weight for '{k}' must be a non-negative number")
    total = sum(weights.values())
    if abs(total - 1.0) > 0.001:
        errors.append(f"Weights sum to {total}, expected 1.0")

    if "C_err" not in config or not isinstance(config["C_err"], (int, float)) or config["C_err"] < 0:
        errors.append("C_err must be a non-negative number")
    if "C_int" not in config or not isinstance(config["C_int"], (int, float)) or config["C_int"] < 0:
        errors.append("C_int must be a non-negative number")

    ph = config.get("provisional_hazard")
    if ph is None or not isinstance(ph, (int, float)) or not (0 <= ph <= 1):
        errors.append("provisional_hazard must be a number in [0,1]")

    floor_axes = config.get("floor_axes", {})
    if not isinstance(floor_axes, dict):
        errors.append("floor_axes must be a dict")
    else:
        for k, v in floor_axes.items():
            if k not in VALID_AXES:
                errors.append(f"Invalid axis '{k}' in floor_axes; must be one of {VALID_AXES}")
            if not isinstance(v, (int, float)) or not (0 <= v <= 1):
                errors.append(f"Floor value for '{k}' must be in [0,1]")
    return errors


def validate_debounce_config(config: Dict[str, Any]) -> List[str]:
    """Return list of error messages; empty if valid."""
    errors = []
    for k, v in config.items():
        if k not in VALID_SIGNAL_TYPES:
            errors.append(f"Unknown signal type '{k}' in debounce config")
        if not isinstance(v, (int, float)) or v < 0:
            errors.append(f"Debounce hours for '{k}' must be a non-negative number, got {v}")
    return errors
