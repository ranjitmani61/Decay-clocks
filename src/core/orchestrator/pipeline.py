"""Governance pipeline: process signals for a node, update state, and log audit."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from src.core.models.node import Node, NodeStatus, AuditLog
from src.core.engine.reliability_dynamics import compute_reliability_vector
from src.core.signals.bus import process_raw_events
from src.core.orchestrator.config_validator import validate_cost_config, validate_debounce_config
from src.core.orchestrator.hazard import GovernanceAction
from src.core.orchestrator.escalation import create_escalation_task
from src.core.utils.metrics import PIPELINE_RUNS, STATE_TRANSITIONS


_SEVERITY = {
    NodeStatus.ACTIVE: 0,
    NodeStatus.PROVISIONAL: 1,
    NodeStatus.IN_REVIEW: 2,
    NodeStatus.SUSPENDED: 3,
    NodeStatus.RETIRED: 4,
}


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _serialize_payload(obj):
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_payload(i) for i in obj]
    return obj


def process_node_lifecycle(
    *,
    node_id: uuid.UUID,
    db: Session,
    catalogue: Dict,
    raw_events: List[Dict],
    now: datetime,
    debounce_config: Dict[str, int],
    cost_config: Dict,
    escalation_deadline_hours: int = 24,
) -> None:
    now_utc = _ensure_utc(now)
    node = db.get(Node, node_id)
    if node is None:
        raise ValueError(f"Node not found: {node_id}")

    cost_errors = validate_cost_config(cost_config)
    if cost_errors:
        raise ValueError("Invalid cost_config: " + "; ".join(cost_errors))
    debounce_errors = validate_debounce_config(debounce_config)
    if debounce_errors:
        raise ValueError("Invalid debounce_config: " + "; ".join(debounce_errors))

    old_status = node.status

    # 1. Update the reliability vector from current state + new signals
    R = node.reliability_vector
    ref_time = node.last_validation_time or node.registration_time
    if ref_time.tzinfo is None:
        ref_time = ref_time.replace(tzinfo=timezone.utc)
    elapsed_days = max(0.0, (now_utc - ref_time).total_seconds() / 86400.0)

    shocks = process_raw_events(
        raw_events=raw_events,
        catalogue=catalogue,
        node_domain_tags=node.domain_tags or [],
        node_class=node.node_class.value,
        now=now_utc,
        memory={},
        debounce_config=debounce_config,
    )

    reg_events, macro_signals, struct_events, drift_metric = [], [], [], None
    for sh in shocks:
        sig = catalogue.get(sh["signal_id"])
        if not sig:
            continue
        cls = sig["signal_class"]
        if cls == "REGULATORY":
            if sh["magnitude"] >= 0.25:
                reg_events.append("major_change")
            else:
                reg_events.append("minor_change")
        elif cls == "MACROECONOMIC":
            macro_signals.append({"magnitude": sh["magnitude"]})
        elif cls == "STRUCTURAL":
            struct_events.append("breaking_change")
        elif cls == "PERFORMANCE":
            drift_metric = sh["magnitude"]
        elif cls == "DEPENDENCY_SHOCK":
            # Directly apply shock values to the child's axes
            for axis, new_val in sh.get("shock", {}).items():
                if axis == "R_s":
                    node.r_s = new_val
                elif axis == "R_p":
                    node.r_p = new_val
                elif axis == "R_c":
                    node.r_c = new_val
                elif axis == "R_r":
                    node.r_r = new_val
                elif axis == "R_t":
                    node.r_t = new_val

    new_R = compute_reliability_vector(
        current_R=R,
        elapsed_days=elapsed_days,
        alpha=node.decay_alpha,
        structural_events=struct_events,
        drift_metric=drift_metric,
        macro_signals=macro_signals,
        regulatory_events=reg_events,
    )
    node.r_s, node.r_p, node.r_c, node.r_r, node.r_t = new_R

    # 2. Compute what the hazard function suggests, but don't downgrade status
    if "hazard_mode" in cost_config and cost_config["hazard_mode"] != "linear":
        from src.core.orchestrator.hazard_nonlinear import compute_governance_action_nonlinear

        suggested_action, hazard, reason = compute_governance_action_nonlinear(new_R, cost_config)
    else:
        from src.core.orchestrator.hazard import compute_governance_action

        suggested_action, hazard, reason = compute_governance_action(new_R, cost_config)

    target_status = {
        GovernanceAction.ACTIVE: NodeStatus.ACTIVE,
        GovernanceAction.PROVISIONAL: NodeStatus.PROVISIONAL,
        GovernanceAction.ESCALATE: NodeStatus.IN_REVIEW,
    }.get(suggested_action, NodeStatus.ACTIVE)

    # 3. Only upgrade status, never downgrade automatically
    if _SEVERITY[target_status] > _SEVERITY[old_status]:
        node.status = target_status
        node.status_changed_at = now_utc
        if target_status == NodeStatus.IN_REVIEW and old_status != NodeStatus.IN_REVIEW:
            create_escalation_task(
                node_id=node.node_id,
                team=node.owner_team,
                reason=f"Governance escalation (hazard={hazard:.3f}, reason={reason})",
                db=db,
                now=now_utc,
                deadline_hours=escalation_deadline_hours,
            )

    if node.status != old_status:
        STATE_TRANSITIONS.labels(
            from_status=old_status.value, to_status=node.status.value
        ).inc()

    payload = {"new_R": list(new_R), "shocks": shocks, "hazard": hazard, "reason": reason}
    db.add(AuditLog(
        node_id=node.node_id,
        event_type="reliability_updated",
        event_payload=_serialize_payload(payload),
    ))
    if node.status != old_status:
        db.add(AuditLog(
            node_id=node.node_id,
            event_type="status_changed",
            event_payload=_serialize_payload({
                "from": old_status.value,
                "to": node.status.value,
                "hazard": hazard,
            }),
        ))

    db.commit()
    PIPELINE_RUNS.inc()
