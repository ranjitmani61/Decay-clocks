"""Tests for the portfolio covariance and risk decomposition engine."""
import numpy as np
import pytest
from src.core.engine.portfolio import (
    compute_hazard_covariance_matrix,
    compute_portfolio_risk_decomposition,
    rank_nodes_by_risk_contribution,
)


class TestCovarianceMatrix:
    def test_identical_series_gives_positive_covariance(self):
        series = {
            "A": [0.1, 0.2, 0.3, 0.4, 0.5],
            "B": [0.1, 0.2, 0.3, 0.4, 0.5],
        }
        cov, ids = compute_hazard_covariance_matrix(series)
        assert cov.shape == (2, 2)
        assert cov[0, 0] > 0   # variance > 0
        assert cov[0, 1] > 0   # positive covariance

    def test_opposite_series_gives_negative_covariance(self):
        series = {
            "A": [0.1, 0.2, 0.3, 0.4, 0.5],
            "B": [0.5, 0.4, 0.3, 0.2, 0.1],
        }
        cov, ids = compute_hazard_covariance_matrix(series)
        assert cov[0, 1] < 0

    def test_single_node_identity(self):
        series = {"X": [0.1, 0.2, 0.3]}
        cov, ids = compute_hazard_covariance_matrix(series)
        assert cov.shape == (1, 1)
        assert ids == ["X"]


class TestRiskDecomposition:
    def test_identical_nodes_share_risk_equally(self):
        hazards = np.array([0.3, 0.3])
        cov = np.array([[0.04, 0.04], [0.04, 0.04]])
        result = compute_portfolio_risk_decomposition(hazards, cov)
        rc = result["risk_contributions"]
        # Both nodes have same hazard and covariance → equal contributions
        assert rc[0] == pytest.approx(rc[1], rel=1e-9)

    def test_risk_contributions_sum_to_volatility(self):
        hazards = np.array([0.2, 0.4, 0.6])
        cov = np.array([[0.01, 0.005, 0.002],
                        [0.005, 0.02, 0.01],
                        [0.002, 0.01, 0.03]])
        result = compute_portfolio_risk_decomposition(hazards, cov)
        rc_sum = float(result["risk_contributions"].sum())
        assert rc_sum == pytest.approx(result["volatility"], rel=1e-9)

    def test_zero_volatility_edge_case(self):
        hazards = np.array([0.0, 0.0])
        cov = np.zeros((2, 2))
        result = compute_portfolio_risk_decomposition(hazards, cov)
        assert result["volatility"] == 0.0
        assert all(result["risk_contributions"] == 0.0)

    def test_relative_contributions_sum_to_one(self):
        hazards = np.array([0.1, 0.3, 0.5])
        cov = np.array([[0.02, 0.01, 0.0],
                        [0.01, 0.03, 0.02],
                        [0.0, 0.02, 0.04]])
        result = compute_portfolio_risk_decomposition(hazards, cov)
        rrc_sum = float(result["relative_contributions"].sum())
        assert rrc_sum == pytest.approx(1.0, rel=1e-9)


class TestRankNodes:
    def test_rank_descending(self):
        hazards = np.array([0.5, 0.1, 0.3])
        cov = np.eye(3) * 0.01
        ranked = rank_nodes_by_risk_contribution(
            ["A", "B", "C"], hazards, cov
        )
        # Highest hazard → highest risk contribution (with identity covariance)
        assert ranked[0][0] == "A"
        assert ranked[2][0] == "B"

    def test_high_covariance_can_elevate_rank(self):
        # Node B has lower hazard but very high covariance with A
        hazards = np.array([0.5, 0.2])
        cov = np.array([[0.01, 0.09], [0.09, 0.01]])
        ranked = rank_nodes_by_risk_contribution(["A", "B"], hazards, cov)
        # A's RC: 0.5*(0.01*0.5+0.09*0.2)/σ
        # B's RC: 0.2*(0.09*0.5+0.01*0.2)/σ
        # B's term (ΣH)₂ = 0.047, A's (ΣH)₁ = 0.023
        # RC_B = 0.2*0.047 = 0.0094, RC_A = 0.5*0.023 = 0.0115
        # So A still higher, but B's MRC is higher
        assert ranked[0][0] == "A"  # A still has higher risk contribution
        assert ranked[1][2] > ranked[0][2]  # B has higher MRC
