"""Multi‑axis reliability state update functions."""
from __future__ import annotations
import math
from typing import List, Dict, Callable, Tuple, Optional

_EPSILON = 1e-3

def _clamp(val: float) -> float:
    if val <= _EPSILON:
        return 0.0
    if val >= 1.0:
        return 1.0
    return val

def update_axis_structural(current_r_s: float, structural_events: List[str]) -> float:
    if any(ev == "breaking_change" for ev in structural_events):
        return 0.2
    return _clamp(current_r_s)

def update_axis_performance(
    current_r_p: float,
    drift_metric: Optional[float] = None,
    drift_mapping: Callable[[float], float] | None = None
) -> float:
    if drift_metric is None:
        return _clamp(current_r_p)
    if drift_mapping is None:
        drift_mapping = lambda d: min(1.0, d)
    penalty = drift_mapping(drift_metric)
    return _clamp(current_r_p - penalty)

def update_axis_context(
    current_r_c: float,
    macro_signals: List[Dict[str, float]]
) -> float:
    if not macro_signals:
        return _clamp(current_r_c)
    total_reduction = sum(s.get("magnitude", 0.0) for s in macro_signals)
    total_reduction = min(total_reduction, 1.0)
    return _clamp(current_r_c - total_reduction)

def update_axis_regulatory(current_r_r: float, regulatory_events: List[str]) -> float:
    for ev in regulatory_events:
        if ev == "major_change":
            return 0.3
        elif ev == "minor_change":
            current_r_r = current_r_r - 0.1
    return _clamp(current_r_r)

def update_axis_temporal(
    current_r_t: float,   # ignored, kept for compatibility
    elapsed_days: float,
    alpha: float
) -> float:
    """Return temporal freshness based purely on elapsed time.
    
    The stored r_t is not used; the correct value is computed from
    the time since last validation, not from the already‑decayed value.
    This prevents compounding decay on repeated pipeline runs.
    """
    if elapsed_days <= 0:
        return 1.0
    return _clamp(math.exp(-alpha * elapsed_days))

def compute_reliability_vector(
    *,
    current_R: Tuple[float, float, float, float, float],
    elapsed_days: float,
    alpha: float,
    structural_events: List[str],
    drift_metric: Optional[float],
    macro_signals: List[Dict[str, float]],
    regulatory_events: List[str],
    drift_mapping: Callable[[float], float] | None = None
) -> Tuple[float, float, float, float, float]:
    r_s, r_p, r_c, r_r, r_t = current_R
    new_r_s = update_axis_structural(r_s, structural_events)
    new_r_p = update_axis_performance(r_p, drift_metric, drift_mapping)
    new_r_c = update_axis_context(r_c, macro_signals)
    new_r_r = update_axis_regulatory(r_r, regulatory_events)
    new_r_t = update_axis_temporal(r_t, elapsed_days, alpha)   # r_t ignored inside
    return (new_r_s, new_r_p, new_r_c, new_r_r, new_r_t)
