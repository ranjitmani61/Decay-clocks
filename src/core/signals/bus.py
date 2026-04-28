"""Signal Bus – pure ingestion, debounce, and matching logic."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Dict, List, Tuple, Any

DEFAULT_DEBOUNCE_HOURS = {
    "structural": 0,
    "regulatory": 24,
    "macroeconomic": 24,
    "behavioural": 24,
    "performance": 0,
}


def debounce_signal(
    signal_type: str,
    event_id: str,
    timestamp: datetime,
    memory: Dict[str, datetime],
    debounce_config: Dict[str, int],
) -> Tuple[bool, Dict[str, datetime]]:
    """Return (allowed, updated_memory). Block if within debounce hours."""
    key = f"{signal_type}:{event_id}"
    last = memory.get(key)
    if last is None:
        memory[key] = timestamp
        return True, memory
    window_hours = debounce_config.get(signal_type, 0)
    if window_hours <= 0:
        memory[key] = timestamp
        return True, memory
    if (timestamp - last).total_seconds() / 3600 < window_hours:
        return False, memory
    memory[key] = timestamp
    return True, memory


def match_signals_to_nodes(
    catalogue: Dict[uuid.UUID, Dict[str, Any]],
    node_domain_tags: List[str],
    node_class: str,
) -> List[Dict[str, Any]]:
    """Return list of catalogue signals that match the given node."""
    tags_set = set(node_domain_tags)
    matches = []
    for sig in catalogue.values():
        if not tags_set.intersection(sig["domain_tags"]):
            continue
        if sig["node_class_affinity"] and node_class not in sig["node_class_affinity"]:
            continue
        matches.append(sig)
    return matches


def process_raw_events(
    raw_events: List[Dict[str, Any]],
    catalogue: Dict[uuid.UUID, Dict[str, Any]],
    node_domain_tags: List[str],
    node_class: str,
    now: datetime,
    memory: Dict[str, datetime],
    debounce_config: Dict[str, int],
) -> List[Dict[str, Any]]:
    """Produce shock events from raw events after debounce and matching."""
    matched_signals = match_signals_to_nodes(catalogue, node_domain_tags, node_class)
    {s["signal_id"]: s for s in matched_signals}
    shocks = []
    for event in raw_events:
        sig_type = event.get("type", "")
        event_tags = set(event.get("domain_tags", []))
        for sig in matched_signals:
            if not event_tags.intersection(sig["domain_tags"]):
                continue
            ev_id = event.get("event_id", str(uuid.uuid4()))
            allowed, memory = debounce_signal(
                sig_type, ev_id, event["timestamp"], memory, debounce_config
            )
            if not allowed:
                continue
            severity = event.get("severity", sig["default_magnitude"])
            magnitude = sig["default_magnitude"] * severity * sig["quality_score"]
            shocks.append({
                "signal_id": sig["signal_id"],
                "magnitude": min(1.0, magnitude),
                "timestamp": event["timestamp"],
            })
            break  # one shock per event
    return shocks
