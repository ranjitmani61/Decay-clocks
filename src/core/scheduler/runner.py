"""Batch scheduler: processes active/provisional nodes, reconciles IN_REVIEW nodes,
and propagates dependency degradation to child nodes."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Dict
from sqlalchemy.orm import Session

from src.core.models.node import Node, NodeStatus, AuditLog, DependencyEdge
from src.core.orchestrator.pipeline import process_node_lifecycle
from src.core.orchestrator.hazard import compute_governance_action
from src.core.utils.metrics import PIPELINE_RUNS, STATE_TRANSITIONS, CSD_WARNINGS
from src.core.engine.csd_integration import check_and_warn_node
from src.core.api.config_loader import get_cost_config_for_node
from src.core.engine.propagation import compute_child_degradation

IN_REVIEW_COOLDOWN_DAYS = 7


def _default_cost_config() -> dict:
    return {
        "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
        "C_err": 500.0,
        "C_int": 1000.0,
        "provisional_hazard": 0.2,
        "floor_axes": {"r": 0.2, "s": 0.3},
    }


def reconcile_in_review_nodes(
    *,
    db: Session,
    now: datetime,
    cost_config: dict | None = None,
) -> int:
    if cost_config is None:
        cost_config = _default_cost_config()
    nodes = db.query(Node).filter(Node.status == NodeStatus.IN_REVIEW).all()
    recovered = 0
    for node in nodes:
        if node.status_changed_at is None:
            continue
        in_review_since = node.status_changed_at
        if (now - in_review_since) < timedelta(days=IN_REVIEW_COOLDOWN_DAYS):
            continue
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


def _apply_dependency_shock(child_node: Node, shock: dict) -> None:
    """Directly apply a shock to the child's reliability axes."""
    for axis, new_val in shock.items():
        if axis == "R_s":
            child_node.r_s = new_val
        elif axis == "R_p":
            child_node.r_p = new_val
        elif axis == "R_c":
            child_node.r_c = new_val
        elif axis == "R_r":
            child_node.r_r = new_val
        elif axis == "R_t":
            child_node.r_t = new_val


def _evaluate_child_status(child_node: Node, cost_config: dict, now: datetime, db: Session) -> None:
    """After a dependency shock, re-evaluate the child's governance status."""
    from src.core.orchestrator.hazard import GovernanceAction
    from src.core.orchestrator.escalation import create_escalation_task

    old_status = child_node.status
    _, hazard = compute_governance_action(child_node.reliability_vector, cost_config)
    suggested_action, _ = compute_governance_action(child_node.reliability_vector, cost_config)

    target_status = {
        GovernanceAction.ACTIVE: NodeStatus.ACTIVE,
        GovernanceAction.PROVISIONAL: NodeStatus.PROVISIONAL,
        GovernanceAction.ESCALATE: NodeStatus.IN_REVIEW,
    }.get(suggested_action, NodeStatus.ACTIVE)

    # Upgrade only
    severity = {
        NodeStatus.ACTIVE: 0,
        NodeStatus.PROVISIONAL: 1,
        NodeStatus.IN_REVIEW: 2,
        NodeStatus.SUSPENDED: 3,
        NodeStatus.RETIRED: 4,
    }
    if severity[target_status] > severity[old_status]:
        child_node.status = target_status
        child_node.status_changed_at = now
        if target_status == NodeStatus.IN_REVIEW and old_status != NodeStatus.IN_REVIEW:
            create_escalation_task(
                node_id=child_node.node_id,
                team=child_node.owner_team,
                reason=f"Dependency propagation: hazard={hazard:.3f}",
                db=db,
                now=now,
                deadline_hours=24,
            )
        STATE_TRANSITIONS.labels(
            from_status=old_status.value, to_status=child_node.status.value
        ).inc()
        db.add(AuditLog(
            node_id=child_node.node_id,
            event_type="status_changed",
            event_payload={
                "from": old_status.value,
                "to": child_node.status.value,
                "reason": "dependency shock propagation",
                "hazard": hazard,
            },
        ))


def propagate_dependency_degradation(
    *,
    parent_node: Node,
    db: Session,
    now: datetime,
    cost_config: dict | None = None,
) -> int:
    """Apply degradation to all children via dependency edges. Returns number of children processed."""
    if cost_config is None:
        cost_config = _default_cost_config()

    edges = (
        db.query(DependencyEdge)
        .filter(DependencyEdge.parent_node_id == parent_node.node_id)
        .all()
    )
    processed = 0
    for edge in edges:
        child = db.get(Node, edge.child_node_id)
        if child is None:
            continue
        shock = compute_child_degradation(
            parent_node.reliability_vector,
            child.reliability_vector,
            edge.propagation_coeffs,
            edge_type=edge.edge_type,
        )
        if not shock:
            continue
        _apply_dependency_shock(child, shock)
        _evaluate_child_status(child, cost_config, now, db)
        processed += 1
    if processed:
        db.commit()
    return processed

    edges = (
        db.query(DependencyEdge)
        .filter(DependencyEdge.parent_node_id == parent_node.node_id)
        .all()
    )
    processed = 0
    for edge in edges:
        child = db.get(Node, edge.child_node_id)
        if child is None:
            continue
        shock = compute_child_degradation(
            parent_node.reliability_vector,
            child.reliability_vector,
            edge.propagation_coeffs,
        )
        if not shock:
            continue
        _apply_dependency_shock(child, shock)
        _evaluate_child_status(child, cost_config, now, db)
        processed += 1
    if processed:
        db.commit()
    return processed


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
            node = db.get(Node, node_id)
            if node is None:
                continue
            process_node_lifecycle(
                node_id=node_id,
                db=db,
                catalogue=catalogue,
                raw_events=[],
                now=now,
                debounce_config=debounce_config,
                cost_config=get_cost_config_for_node(node, db),
            )
            PIPELINE_RUNS.inc()
            count += 1

            # Propagate degradation
            propagate_dependency_degradation(
                parent_node=node,
                db=db,
                now=now,
                cost_config=cost_config,
            )
        except ValueError:
            db.rollback()
            continue

    recovered = reconcile_in_review_nodes(db=db, now=now, cost_config=cost_config)
    count += recovered
    return count
