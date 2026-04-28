"""Autonomous resilience engine."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional

def should_auto_suspend(
    criticality: str,
    deadline: datetime,
    now: datetime,
    escalation_status: str,
) -> Optional[str]:
    if now <= deadline:
        return None
    if criticality == "CRITICAL":
        return "SUSPEND"
    if criticality == "HIGH":
        if now - deadline >= timedelta(hours=24):
            return "SUSPEND"
        return None
    # STANDARD: retire after 14 days overdue
    if now - deadline >= timedelta(days=14):
        return "RETIRE"
    return None


def surge_calm(
    current_provisional: float,
    current_review: float,
    active_escalations: int,
    threshold: int = 100,
) -> tuple[float, float]:
    if active_escalations <= threshold:
        return (current_provisional, current_review)
    overload = min(active_escalations - threshold, threshold)
    ramp = overload / threshold
    new_prov = current_provisional + ramp * 0.2
    new_rev = current_review + ramp * 0.15
    return (min(0.9, new_prov), min(0.8, new_rev))


def should_batch_review(
    num_nodes_same_domain: int,
    threshold: int,
) -> bool:
    return num_nodes_same_domain >= threshold
