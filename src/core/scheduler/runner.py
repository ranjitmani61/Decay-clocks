"""Batch scheduler: periodically processes all active decision nodes."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session

from src.core.models.node import Node, NodeStatus
from src.core.orchestrator.pipeline import process_node_lifecycle


def run_scheduled_cycle(
    *,
    db: Session,
    catalogue: Dict,
    now: datetime,
    cost_config: Dict,
    debounce_config: Dict,
) -> int:
    """Process all nodes with status ACTIVE or PROVISIONAL.
    
    Returns the number of nodes processed.
    """
    # Fetch all relevant node IDs (avoid server‑side cursors for simplicity)
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
                raw_events=[],          # scheduled cycle applies only time decay
                now=now,
                debounce_config=debounce_config,
                cost_config=cost_config,
            )
            count += 1
        except ValueError:
            # If node deleted mid‑cycle, rollback and skip
            db.rollback()
            continue
    return count
