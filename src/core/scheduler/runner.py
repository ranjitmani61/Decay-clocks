"""Batch scheduler: periodically processes all active decision nodes."""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict
from sqlalchemy.orm import Session

from src.core.models.node import Node, NodeStatus, AuditLog
from src.core.orchestrator.pipeline import process_node_lifecycle
from src.core.orchestrator.hazard import compute_governance_action
from src.core.utils.metrics import PIPELINE_RUNS, STATE_TRANSITIONS

IN_REVIEW_COOLDOWN_DAYS = 7


def _default_cost_config() -> dict:
    return {
        "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
        "C_err": 500.0,
        "C_int": 1000.0,
        "provisional_hazard": 0.2,
        "floor_axes": {"r": 0.2, "s": 0.1},
    }


def reconcile_in_review_nodes(
    *,
    db: Session,
    now: datetime,
    cost_config: dict | None = None,
) -> int:
    """Return IN_REVIEW nodes to ACTIVE if hazard has decayed below provisional
    threshold for longer than the cooldown period.
    Uses node.status_changed_at as the single source of truth.
    """
    if cost_config is None:
        cost_config = _default_cost_config()

    nodes = db.query(Node).filter(Node.status == NodeStatus.IN_REVIEW).all()
    recovered = 0

    for node in nodes:
        # How long has it been in review?
        if node.status_changed_at is None:
            # Never auto‑recover if we don’t know when it entered IN_REVIEW
            continue
            # Never auto‑recover if we don’t know when it entered IN_REVIEW
            continue
            continue
        in_review_since = node.status_changed_at
        if (now - in_review_since) < timedelta(days=IN_REVIEW_COOLDOWN_DAYS):
            continue

        # Recompute hazard using current R(t)
        _, hazard = compute_governance_action(node.reliability_vector, cost_config)

        if hazard < cost_config["provisional_hazard"]:
            old_status = node.status
            node.status = NodeStatus.ACTIVE
            node.status_changed_at = now
            STATE_TRANSITIONS.labels(
                from_status=old_status.value, to_status=NodeStatus.ACTIVE.value
            ).inc()
            db.add(AuditLog(
                node_id=node.node_id,
                event_type="status_changed",
                event_payload={
                    "from": old_status.value,
                    "to": NodeStatus.ACTIVE.value,
                    "reason": "auto-recovery: hazard below provisional threshold after cooldown",
                    "hazard": hazard,
                },
            ))
            recovered += 1

    if recovered:
        db.commit()
    return recovered


def run_scheduled_cycle(
    *,
    db: Session,
    catalogue: Dict,
    now: datetime,
    cost_config: Dict | None = None,
    debounce_config: Dict | None = None,
) -> int:
    if cost_config is None:
        cost_config = _default_cost_config()
    if debounce_config is None:
        debounce_config = {}

    rows = (
        db.query(Node.node_id)
        .filter(Node.status.in_([NodeStatus.ACTIVE, NodeStatus.PROVISIONAL]))
        .all()
    )
    count = 0
    for (node_id,) in rows:
        try:
            process_node_lifecycle(
                node_id=node_id,
                db=db,
                catalogue=catalogue,
                raw_events=[],
                now=now,
                debounce_config=debounce_config,
                cost_config=cost_config,
            )
            PIPELINE_RUNS.inc()
            count += 1
        except ValueError:
            db.rollback()
            continue

    recovered = reconcile_in_review_nodes(db=db, now=now, cost_config=cost_config)
    count += recovered

    return count
