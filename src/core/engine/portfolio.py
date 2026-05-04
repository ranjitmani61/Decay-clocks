"""Portfolio covariance engine – Markowitz risk decomposition for governance nodes.

Computes the hazard covariance matrix from audit‑log time series and decomposes
total portfolio risk into per‑node contributions. No reviewer allocation yet.
"""
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import numpy as np
from sqlalchemy.orm import Session
from src.core.models.node import AuditLog
import json


def extract_hazard_series(
    node_ids: List[str],
    db: Session,
    min_history: int = 20,
) -> Dict[str, List[float]]:
    """Return a dict mapping node_id → list of hazard values (newest last).

    Nodes with fewer than min_history data points are excluded.
    """
    series: Dict[str, List[float]] = {}
    for nid in node_ids:
        events = (
            db.query(AuditLog)
            .filter(
                AuditLog.node_id == nid,
                AuditLog.event_type == "reliability_updated",
            )
            .order_by(AuditLog.created_at.asc())
            .all()
        )
        hazards = []
        for ev in events:
            payload = ev.event_payload
            if isinstance(payload, str):
                payload = json.loads(payload)
            h = payload.get("hazard")
            if h is not None:
                hazards.append(float(h))
        if len(hazards) >= min_history:
            series[nid] = hazards
    return series


def compute_hazard_covariance_matrix(
    series: Dict[str, List[float]],
) -> Tuple[np.ndarray, List[str]]:
    """Compute the N×N covariance matrix of hazard time series.

    Returns (cov_matrix, ordered_node_ids).
    Uses numpy.cov with rowvar=True (each row is a variable/node).
    """
    ordered = list(series.keys())
    if len(ordered) < 2:
        return np.zeros((1, 1)), ordered

    # Align all series to the same length (use the shortest)
    min_len = min(len(s) for s in series.values())
    data = np.array([series[nid][-min_len:] for nid in ordered])
    cov = np.cov(data)  # rowvar=True by default
    return cov, ordered


def compute_portfolio_risk_decomposition(
    hazards: np.ndarray,       # shape (N,) current hazard values
    cov_matrix: np.ndarray,    # shape (N, N) covariance matrix
) -> Dict[str, np.ndarray]:
    """Decompose portfolio risk into per‑node contributions.

    Portfolio variance: sigma**2 = H.T @ Sigma @ H
    Portfolio volatility: sigma = sqrt(sigma**2)
    Risk contribution: RC_i = H_i * (Sigma @ H)_i / sigma
    Marginal risk contribution: MRC_i = (Sigma @ H)_i / sigma

    Returns dict with keys: 'variance', 'volatility', 'risk_contributions',
    'marginal_contributions', 'relative_contributions'.
    """
    sigma_h = cov_matrix @ hazards       # Sigma @ H
    variance = float(hazards @ sigma_h)  # H.T @ Sigma @ H
    volatility = np.sqrt(max(variance, 0.0))

    if volatility < 1e-10:
        n = len(hazards)
        return {
            "variance": 0.0,
            "volatility": 0.0,
            "risk_contributions": np.zeros(n),
            "marginal_contributions": np.zeros(n),
            "relative_contributions": np.zeros(n),
        }

    rc = hazards * sigma_h / volatility           # RC_i
    mrc = sigma_h / volatility                    # MRC_i
    rrc = rc / rc.sum() if rc.sum() > 0 else np.zeros_like(rc)  # relative

    return {
        "variance": variance,
        "volatility": float(volatility),
        "risk_contributions": rc,
        "marginal_contributions": mrc,
        "relative_contributions": rrc,
    }


def rank_nodes_by_risk_contribution(
    node_ids: List[str],
    hazards: np.ndarray,
    cov_matrix: np.ndarray,
) -> List[Tuple[str, float, float]]:
    """Return nodes sorted by risk contribution (highest first).

    Each entry: (node_id, risk_contribution, marginal_contribution)
    """
    decomp = compute_portfolio_risk_decomposition(hazards, cov_matrix)
    rc = decomp["risk_contributions"]
    mrc = decomp["marginal_contributions"]
    ranked = sorted(
        zip(node_ids, rc, mrc),
        key=lambda x: x[1],
        reverse=True,
    )
    return [(nid, float(r), float(m)) for nid, r, m in ranked]
