"""Critical Slowing Down – early‑warning signals from reliability time series."""
from __future__ import annotations
import math
from typing import List, Tuple, Dict, Optional


def rolling_variance(series: List[float]) -> float:
    """Return the population variance of a list of floats."""
    n = len(series)
    if n < 2:
        return 0.0
    mean = sum(series) / n
    return sum((x - mean) ** 2 for x in series) / n


def lag1_autocorr(series: List[float]) -> float:
    """Return the lag‑1 Pearson autocorrelation of a list of floats."""
    n = len(series)
    if n < 3:
        return 0.0
    x = series[:-1]
    y = series[1:]
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    den_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
    if den_x == 0.0 or den_y == 0.0:
        return 0.0
    return num / (den_x * den_y)


def compute_csd_warnings(
    axis_history: Dict[str, List[float]],
    var_threshold: float = 0.02,
    ac_threshold: float = 0.5,
    min_window: int = 20,
) -> Dict[str, Optional[str]]:
    """Return early‑warning signals for each axis.

    An axis triggers a warning when both its rolling variance and lag‑1
    autocorrelation exceed the given thresholds, provided the history
    contains at least `min_window` data points.

    Returns a dict mapping axis name → warning message (or None if silent).
    """
    warnings: Dict[str, Optional[str]] = {}
    for axis, values in axis_history.items():
        if len(values) < min_window:
            warnings[axis] = None
            continue
        var = rolling_variance(values)
        ac = lag1_autocorr(values)
        if var > var_threshold and ac > ac_threshold:
            warnings[axis] = (
                f"Critical slowing down detected for axis {axis}: "
                f"variance={var:.4f}, autocorr={ac:.4f}"
            )
        else:
            warnings[axis] = None
    return warnings
