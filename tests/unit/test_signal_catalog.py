"""Test the Signal Catalogue registry – pure, state‑passed as argument."""
import pytest
import uuid
from src.core.signals.catalogue import (
    create_signal,
    get_signal,
    update_quality_score,
    find_signals_for_node,
)

@pytest.fixture
def empty_catalog():
    return {}

def test_create_signal_adds_entry(empty_catalog):
    sid = create_signal(
        empty_catalog,
        signal_class="REGULATORY",
        domain_tags=["credit", "EU"],
        default_magnitude=0.35,
        node_class_affinity=["ML_MODEL", "BUSINESS_RULE_SET"],
    )
    assert sid is not None
    rec = empty_catalog.get(sid)
    assert rec["signal_class"] == "REGULATORY"
    assert rec["domain_tags"] == ["credit", "EU"]
    assert rec["default_magnitude"] == 0.35
    assert rec["node_class_affinity"] == ["ML_MODEL", "BUSINESS_RULE_SET"]
    assert rec["quality_score"] == 1.0

def test_get_signal_returns_none_for_unknown(empty_catalog):
    assert get_signal(empty_catalog, uuid.uuid4()) is None

def test_update_quality_score_modifies_entry(empty_catalog):
    sid = create_signal(empty_catalog, "MACROECONOMIC", ["US"], 0.2, ["ML_MODEL"])
    update_quality_score(empty_catalog, sid, 0.7)
    assert empty_catalog[sid]["quality_score"] == 0.7

def test_find_signals_for_node_filters_by_tags_and_affinity(empty_catalog):
    sid1 = create_signal(empty_catalog, "REGULATORY", ["EU"], 0.4,
                         ["ML_MODEL"])
    sid2 = create_signal(empty_catalog, "REGULATORY", ["EU"], 0.3,
                         ["BUSINESS_RULE_SET"])
    sid3 = create_signal(empty_catalog, "MACROECONOMIC", ["US"], 0.1,
                         ["ML_MODEL"])
    # node with tags ["EU"], class "ML_MODEL"
    results = find_signals_for_node(empty_catalog,
                                    node_domain_tags=["EU"],
                                    node_class="ML_MODEL")
    # Should match sid1 (EU + ML_MODEL) and maybe sid2? sid2 has BUSINESS_RULE_SET affinity, not ML_MODEL -> excluded
    # sid3 has US tag, not EU -> excluded
    assert len(results) == 1
    assert results[0]["signal_id"] == sid1

def test_find_signals_returns_empty_if_none_match(empty_catalog):
    create_signal(empty_catalog, "REGULATORY", ["US"], 0.3, ["ML_MODEL"])
    res = find_signals_for_node(empty_catalog, node_domain_tags=["EU"],
                                node_class="ML_MODEL")
    assert res == []
