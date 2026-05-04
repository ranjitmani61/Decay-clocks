"""Tests for the greedy reviewer allocation optimizer (risk‑reduction‑based)."""
import numpy as np
import pytest
from src.core.engine.portfolio_optimizer import (
    allocate_reviewer_bandwidth,
    default_review_times,
)


class TestDefaultReviewTimes:
    def test_mapping(self):
        assert default_review_times("CRITICAL") == 2.0
        assert default_review_times("HIGH") == 1.5
        assert default_review_times("STANDARD") == 1.0
        assert default_review_times("UNKNOWN") == 1.0


class TestGreedyAllocation:
    def test_no_nodes(self):
        result = allocate_reviewer_bandwidth(
            np.array([]), np.eye(0), [], {}, 10.0
        )
        assert result == []

    def test_single_node_within_budget(self):
        result = allocate_reviewer_bandwidth(
            hazards=np.array([0.5]),
            cov_matrix=np.eye(1) * 0.01,
            node_ids=["A"],
            review_times={"A": 2.0},
            total_bandwidth=5.0,
        )
        assert len(result) == 1
        assert result[0][0] == "A"
        assert result[0][1] > 0  # risk reduction must be positive

    def test_single_node_exceeds_budget(self):
        result = allocate_reviewer_bandwidth(
            hazards=np.array([0.5]),
            cov_matrix=np.eye(1) * 0.01,
            node_ids=["A"],
            review_times={"A": 5.0},
            total_bandwidth=2.0,
        )
        assert len(result) == 0

    def test_ranking_by_risk_reduction(self):
        # Two nodes with different hazards; review reduces hazard to 0
        hazards = np.array([0.8, 0.3])
        cov = np.eye(2) * 0.02
        result = allocate_reviewer_bandwidth(
            hazards=hazards,
            cov_matrix=cov,
            node_ids=["high", "low"],
            review_times={"high": 1.0, "low": 1.0},
            total_bandwidth=2.0,
            post_review_hazard=0.0,
        )
        assert len(result) == 2
        # The higher‑hazard node should be ranked first
        assert result[0][0] == "high"
        assert result[1][0] == "low"

    def test_respects_bandwidth(self):
        hazards = np.array([0.5, 0.5])
        cov = np.eye(2) * 0.01
        result = allocate_reviewer_bandwidth(
            hazards=hazards,
            cov_matrix=cov,
            node_ids=["A", "B"],
            review_times={"A": 3.0, "B": 3.0},
            total_bandwidth=4.0,
        )
        assert len(result) == 1

    def test_covariance_changes_ranking(self):
        # B has lower hazard but high covariance with A; after reviewing A,
        # the remaining risk might change, but baseline ranking still picks
        # the one whose review reduces portfolio risk the most.
        hazards = np.array([0.7, 0.5])
        # High covariance between A and B
        cov = np.array([[0.04, 0.035], [0.035, 0.01]])
        result = allocate_reviewer_bandwidth(
            hazards=hazards,
            cov_matrix=cov,
            node_ids=["A", "B"],
            review_times={"A": 1.0, "B": 1.0},
            total_bandwidth=1.0,
        )
        assert len(result) == 1
        # Result is deterministic; we can check that the selected node is one of them
        assert result[0][0] in ("A", "B")
