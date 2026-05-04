"""Helpers to extract reliability time series from the audit log and trigger CSD."""
from __future__ import annotations
import json
from typing import Dict, List
from sqlalchemy.orm import Session
from src.core.models.node import AuditLog, Node, NodeStatus
from src.core.engine.csd import compute_csd_warnings
from src.core.utils.metrics import CSD_WARNINGS


def get_reliability_history(
    node_id: str, db: Session, limit: int = 30
) -> Dict[str, List[float]]:
    """Return the last `limit` reliability snapshots for a node.

    The result is a dict mapping axis name → list of values (newest last).
    """
    events = (
        db.query(AuditLog)
        .filter(
            AuditLog.node_id == node_id,
            AuditLog.event_type == "reliability_updated",
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    # events are newest‑first; we want oldest‑first
    events = list(reversed(events))
    history = {"R_s": [], "R_p": [], "R_c": [], "R_r": [], "R_t": []}
    for ev in events:
        payload = ev.event_payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        new_r = payload.get("new_R")
        if new_r and len(new_r) == 5:
            history["R_s"].append(new_r[0])
            history["R_p"].append(new_r[1])
            history["R_c"].append(new_r[2])
            history["R_r"].append(new_r[3])
            history["R_t"].append(new_r[4])
    return history


def check_and_warn_node(node: Node, db: Session) -> bool:
    """Run CSD detection for one node. If a warning fires, record it.

    Returns True if a warning was raised, False otherwise.
    """
    history = get_reliability_history(node.node_id, db)
    warnings = compute_csd_warnings(history)
    fired = False
    for axis, msg in warnings.items():
        if msg is not None:
            db.add(AuditLog(
                node_id=node.node_id,
                event_type="csd_warning",
                event_payload={"axis": axis, "message": msg},
            ))
            fired = True
            CSD_WARNINGS.inc()
    if fired and node.status == NodeStatus.ACTIVE:
        node.status = NodeStatus.PRE_FAILURE_WARNING
    if fired:
        db.commit()
    return fired
