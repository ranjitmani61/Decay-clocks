"""Dependency propagation – pure functions to compute synthetic degradation signals."""

def compute_child_degradation(parent_R: tuple, child_R: tuple, coeffs: dict, edge_type: str = "") -> dict:
    axis_names = ["R_s", "R_p", "R_c", "R_r", "R_t"]
    parent_values = dict(zip(axis_names, parent_R))
    child_values = dict(zip(axis_names, child_R))

    shock = {}
    for axis, coeff in coeffs.items():
        parent_val = parent_values[axis]
        child_val = child_values[axis]
        if parent_val < child_val:
            if edge_type == "SCHEMA_DEP" and axis == "R_s":
                # Structural dependency: child cannot be better than parent
                new_val = parent_val
            else:
                # Standard blending
                degradation = coeff * (child_val - parent_val)
                new_val = child_val - degradation
            shock[axis] = max(0.0, min(1.0, new_val))
    return shock
