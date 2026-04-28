"""Pure Signal Catalogue management – all state passed explicitly.

No global mutable state. Follows TDD, scalable (stateless), observable.
"""
from __future__ import annotations
import uuid
from typing import Dict, List, Optional, Any

# ── Catalogue operations ──────────────────────────────

def create_signal(
    catalog: Dict[uuid.UUID, Dict[str, Any]],
    signal_class: str,
    domain_tags: List[str],
    default_magnitude: float,
    node_class_affinity: List[str],
) -> uuid.UUID:
    """Add a signal type to the catalogue. Returns its ID."""
    sid = uuid.uuid4()
    catalog[sid] = {
        "signal_id": sid,
        "signal_class": signal_class,
        "domain_tags": domain_tags,
        "default_magnitude": default_magnitude,
        "node_class_affinity": node_class_affinity,
        "quality_score": 1.0,
    }
    return sid

def get_signal(
    catalog: Dict[uuid.UUID, Dict[str, Any]], signal_id: uuid.UUID
) -> Optional[Dict[str, Any]]:
    """Retrieve a signal by ID, or None."""
    return catalog.get(signal_id)

def update_quality_score(
    catalog: Dict[uuid.UUID, Dict[str, Any]],
    signal_id: uuid.UUID,
    new_score: float,
) -> None:
    """Set a new quality_score for a signal (0..1)."""
    if signal_id in catalog:
        catalog[signal_id]["quality_score"] = max(0.0, min(1.0, new_score))

def find_signals_for_node(
    catalog: Dict[uuid.UUID, Dict[str, Any]],
    node_domain_tags: List[str],
    node_class: str,
) -> List[Dict[str, Any]]:
    """Return all signals that match the node's domain tags AND class affinity."""
    node_tags_set = set(node_domain_tags)
    matches = []
    for sig in catalog.values():
        # Check domain tag intersection
        if not node_tags_set.intersection(sig["domain_tags"]):
            continue
        # Check node class affinity (empty affinity list = all)
        if sig["node_class_affinity"] and node_class not in sig["node_class_affinity"]:
            continue
        matches.append(sig)
    return matches
