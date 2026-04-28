"""Unit tests for the autonomous resilience engine."""
import pytest
from datetime import datetime, timezone, timedelta
from src.core.orchestrator.resilience import (
    should_auto_suspend,
    surge_calm,
    should_batch_review,
)

class TestAutoSuspend:
    def test_critical_node_past_deadline_suspends(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = now - timedelta(hours=1)  # 1 hour late
        action = should_auto_suspend(
            criticality="CRITICAL",
            deadline=deadline,
            now=now,
            escalation_status="IN_PROGRESS",
        )
        assert action == "SUSPEND"

    def test_standard_node_past_deadline_retires(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = now - timedelta(days=14)  # 14 days late
        action = should_auto_suspend(
            criticality="STANDARD",
            deadline=deadline,
            now=now,
            escalation_status="PENDING",
        )
        assert action == "RETIRE"

    def test_task_not_yet_due_remains(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = now + timedelta(hours=5)
        action = should_auto_suspend(
            criticality="HIGH",
            deadline=deadline,
            now=now,
            escalation_status="IN_PROGRESS",
        )
        assert action is None


class TestSurgeCalm:
    def test_low_queue_no_change(self):
        new_prov, new_review = surge_calm(
            current_provisional=0.3,
            current_review=0.2,
            active_escalations=50,
            threshold=100,   # surge limit
        )
        assert new_prov == 0.3
        assert new_review == 0.2

    def test_above_surge_threshold_raises(self):
        new_prov, new_review = surge_calm(
            current_provisional=0.3,
            current_review=0.2,
            active_escalations=250,
            threshold=100,
        )
        # Both thresholds raised to reduce sensitivity
        assert new_prov > 0.3
        assert new_review > 0.2
        assert new_prov <= 0.9
        assert new_review <= 0.8

    def test_max_cap(self):
        # Already high thresholds, surge shouldn't push beyond safe limits
        new_prov, new_review = surge_calm(
            current_provisional=0.85,
            current_review=0.75,
            active_escalations=1000,
            threshold=10,
        )
        assert new_prov <= 0.9
        assert new_review <= 0.8


class TestBatchReview:
    def test_single_node_no_batch(self):
        assert not should_batch_review(1, 50)

    def test_many_nodes_in_same_domain_batch(self):
        assert should_batch_review(80, 50)

    def test_exactly_at_limit(self):
        assert should_batch_review(50, 50)  # edge: no batch (0‑based?)
