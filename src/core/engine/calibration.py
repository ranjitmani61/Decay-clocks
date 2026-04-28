"""Bayesian calibration functions for governance parameters.

All functions are pure, stateless, and auditable.
"""
from __future__ import annotations
import math

# --- Signal quality (Beta‑Binomial conjugate model) ---

def update_signal_quality(
    alpha: float, beta: float, review_outcome: bool
) -> tuple[float, float]:
    """Update Beta distribution parameters after a human review.

    Args:
        alpha: prior successes + 1
        beta: prior failures + 1
        review_outcome: True if signal contributed to staleness, False otherwise.

    Returns:
        (new_alpha, new_beta)
    """
    if alpha <= 0 or beta <= 0:
        raise ValueError("Alpha and beta must be positive")
    if review_outcome:
        return (alpha + 1.0, beta)
    else:
        return (alpha, beta + 1.0)


# --- Half‑life adjustment ---

_MIN_HALF_LIFE_DAYS = 5.0
_MAX_HALF_LIFE_DAYS = 365.0 * 5   # 5 years


def update_half_life(
    current_half_life: float,
    elapsed_days_since_valid: float,
    node_was_stale: bool,
    c_t_at_review: float   # currently not used directly; reserved for future weighting
) -> float:
    """Adjust half‑life based on review timing relative to the current estimate.

    - If node was found stale *before* the half‑life had fully elapsed,
      the half‑life is too long → shorten it.
    - If node was still healthy *after* the half‑life had elapsed,
      the half‑life is too short → lengthen it.
    - Otherwise, keep it unchanged.

    The adjustment is proportional to the ratio (elapsed / current_half_life),
    clamped to a reasonable range.

    Args:
        current_half_life: current nominal half‑life in days.
        elapsed_days_since_valid: days between last validation and review.
        node_was_stale: True if reviewer marked node as stale.
        c_t_at_review: (unused) retained for signature compatibility.

    Returns:
        New half‑life (clamped).
    """
    if elapsed_days_since_valid <= 0:
        return current_half_life

    ratio = elapsed_days_since_valid / current_half_life
    # Prevent extreme ratio swings
    ratio = max(0.5, min(2.0, ratio))

    if node_was_stale and ratio < 1.0:
        # Node became stale earlier than half‑life predicted → shorten half‑life
        new_hl = current_half_life * ratio
    elif not node_was_stale and ratio > 1.0:
        # Node survived longer than half‑life predicted → lengthen half‑life
        new_hl = current_half_life * ratio
    else:
        new_hl = current_half_life

    # Clamp to absolute bounds
    return max(_MIN_HALF_LIFE_DAYS, min(_MAX_HALF_LIFE_DAYS, new_hl))


# --- Threshold adaptation ---

_MIN_THRESHOLD = 0.01
_MAX_THRESHOLD = 0.99


def adjust_threshold(
    current_threshold: float,
    false_positive_rate: float,
    desired_fpr: float = 0.1,
    step: float = 0.02
) -> float:
    """Adjust a governance threshold toward a desired false‑positive rate.

    Args:
        current_threshold: current value (e.g., provisional_hazard).
        false_positive_rate: observed FPR over a recent window.
        desired_fpr: target FPR (default 0.1).
        step: maximum change per update.

    Returns:
        New threshold (clamped).
    """
    error = false_positive_rate - desired_fpr
    if error > 0:
        # Too many false positives → lower threshold (make it harder to trigger)
        new_th = current_threshold - min(step, error * 0.5)
    elif error < 0:
        # Too few → raise threshold
        new_th = current_threshold + min(step, -error * 0.5)
    else:
        return current_threshold

    return max(_MIN_THRESHOLD, min(_MAX_THRESHOLD, new_th))
