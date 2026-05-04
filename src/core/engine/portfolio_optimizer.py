"""Greedy reviewer‑allocation optimizer using portfolio risk decomposition.

Uses actual portfolio risk reduction (baseline − post‑review risk) to rank
nodes by their marginal benefit per unit of review time. Still greedy, but
now grounded in recomputed risk rather than a heuristic.
"""
from __future__ import annotations
from typing import List, Dict, Tuple
import numpy as np
from src.core.engine.portfolio import compute_portfolio_risk_decomposition


def allocate_reviewer_bandwidth(
    hazards: np.ndarray,
    cov_matrix: np.ndarray,
    node_ids: List[str],
    review_times: Dict[str, float],
    total_bandwidth: float,
    post_review_hazard: float = 0.0,
    min_history_fallback: bool = False,
) -> List[Tuple[str, float, float, float]]:
    """Return an ordered list of nodes to review, respecting time budget.

    Each entry: (node_id, risk_reduction, review_time, cumulative_time).
    Nodes not fitting in the budget are omitted.

    Risk reduction is computed as:
      baseline_volatility − portfolio_volatility_after_review_i

    Args:
        hazards: current hazard values (length N)
        cov_matrix: N×N covariance matrix
        node_ids: list of node IDs (order matches hazards/cov_matrix)
        review_times: dict mapping node_id → estimated review hours
        total_bandwidth: total reviewer‑hours available
        post_review_hazard: hazard value after review (default 0 = fully reset)
        min_history_fallback: if True, rank by hazard only (no covariance)
    """
    n = len(node_ids)
    if n == 0:
        return []

    # Baseline portfolio volatility
    baseline_decomp = compute_portfolio_risk_decomposition(hazards, cov_matrix)
    baseline_vol = baseline_decomp["volatility"]

    # For each node, compute risk reduction after "reviewing" that node
    scored = []
    for i, nid in enumerate(node_ids):
        rt = review_times.get(nid, 1.0)
        # Simulate post‑review hazard vector
        post_hazards = hazards.copy()
        post_hazards[i] = post_review_hazard

        # Recompute portfolio risk
        post_decomp = compute_portfolio_risk_decomposition(post_hazards, cov_matrix)
        post_vol = post_decomp["volatility"]

        risk_reduction = baseline_vol - post_vol
        # Can be negative in edge cases (covariance structure); clamp to 0.
        risk_reduction = max(0.0, risk_reduction)

        score = risk_reduction / rt if rt > 0 else 0.0
        scored.append((nid, risk_reduction, rt, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[3], reverse=True)

    # Greedy selection
    selected: List[Tuple[str, float, float, float]] = []
    cumulative_time = 0.0
    for nid, risk_red, rt, score in scored:
        if cumulative_time + rt <= total_bandwidth:
            cumulative_time += rt
            selected.append((nid, risk_red, rt, cumulative_time))

    return selected


def default_review_times(node_criticality: str) -> float:
    """Return a default review time based on criticality."""
    mapping = {
        "CRITICAL": 2.0,
        "HIGH": 1.5,
        "STANDARD": 1.0,
    }
    return mapping.get(node_criticality, 1.0)
