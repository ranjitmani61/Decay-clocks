"""Output Wrapper: annotates every decision with governance provenance."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy.orm import Session

from src.core.models.node import Node, NodeStatus
from src.core.orchestrator.hazard import compute_governance_action
from src.core.api.config_loader import get_active_cost_config


def wrap_decision(
    *,
    node_id: uuid.UUID,
    original_output: Dict[str, Any],
    db: Session,
) -> Dict[str, Any]:
    """Return a copy of original_output with a __provenance__ block.

    The block contains:
        - node_id
        - reliability_vector (snapshot of R(t))
        - provisional (bool)
        - status
        - hazard (computed from current R(t) and active cost config)
        - timestamp (UTC)
    """
    node = db.get(Node, node_id)
    if node is None:
        raise ValueError(f"Node not found: {node_id}")

    # Compute current hazard using the active cost config
    cost_cfg = get_active_cost_config(db)
    _, hazard = compute_governance_action(node.reliability_vector, cost_cfg)

    provenance = {
        "node_id": str(node.node_id),
        "node_class": node.node_class.value,
        "reliability": {
            "r_s": node.r_s,
            "r_p": node.r_p,
            "r_c": node.r_c,
            "r_r": node.r_r,
            "r_t": node.r_t,
        },
        "status": node.status.value,
        "provisional": node.status in (NodeStatus.PROVISIONAL, NodeStatus.IN_REVIEW),
        "hazard": round(hazard, 4),
        "threshold": round(cost_cfg.get("provisional_hazard", 0.2), 4),
        "decision": "PROVISIONAL" if node.status in (NodeStatus.PROVISIONAL, NodeStatus.IN_REVIEW) else "ACTIVE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    wrapped = dict(original_output)
    wrapped["__provenance__"] = provenance
    return wrapped
