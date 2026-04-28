"""Escalation Dispatcher: creates human‑review tasks in the database."""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.core.models.node import Node, EscalationTask


def create_escalation_task(
    *,
    node_id: uuid.UUID,
    team: str,
    reason: str,
    db: Session,
    now: datetime,
    deadline_hours: int = 24,
) -> uuid.UUID:
    """Create an escalation task for a node. Returns the new task ID."""
    node = db.get(Node, node_id)
    if node is None:
        raise ValueError(f"Node not found: {node_id}")

    deadline = now + timedelta(hours=deadline_hours)
    task = EscalationTask(
        node_id=node_id,
        assigned_team=team,
        notes=reason,
        deadline=deadline,
    )
    db.add(task)
    db.commit()
    return task.id
