"""Test Signal Bus: debounce, matching, event processing."""
import uuid
import pytest
from datetime import datetime, timedelta
from src.core.signals.bus import debounce_signal, match_signals_to_nodes, process_raw_events

# Proper UUIDs
SIG_REG = uuid.UUID("11111111-1111-1111-1111-111111111111")
SIG_MACRO = uuid.UUID("22222222-2222-2222-2222-222222222222")

CAT = {
    SIG_REG: {
        "signal_id": SIG_REG,
        "signal_class": "REGULATORY",
        "domain_tags": ["EU"],
        "default_magnitude": 0.3,
        "node_class_affinity": ["ML_MODEL"],
        "quality_score": 0.9,
    },
    SIG_MACRO: {
        "signal_id": SIG_MACRO,
        "signal_class": "MACROECONOMIC",
        "domain_tags": ["US"],
        "default_magnitude": 0.15,
        "node_class_affinity": ["ML_MODEL"],
        "quality_score": 1.0,
    },
}

DEBOUNCE_CFG = {"structural": 0, "regulatory": 24, "macroeconomic": 24}


class TestDebounce:
    def test_structural_immediate(self):
        mem = {}
        now = datetime(2026, 1, 1, 12, 0, 0)
        ok, mem = debounce_signal("structural", "ev1", now, mem, DEBOUNCE_CFG)
        assert ok

    def test_regulatory_blocked_within_window(self):
        mem = {}
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        ok, mem = debounce_signal("regulatory", "ev2", t0, mem, DEBOUNCE_CFG)
        assert ok
        t1 = t0 + timedelta(hours=10)
        ok2, _ = debounce_signal("regulatory", "ev2", t1, mem, DEBOUNCE_CFG)
        assert not ok2

    def test_regulatory_allowed_after_window(self):
        mem = {}
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        ok, mem = debounce_signal("regulatory", "ev3", t0, mem, DEBOUNCE_CFG)
        assert ok
        t1 = t0 + timedelta(hours=25)
        ok2, _ = debounce_signal("regulatory", "ev3", t1, mem, DEBOUNCE_CFG)
        assert ok2


class TestMatching:
    def test_by_tag_and_class(self):
        res = match_signals_to_nodes(CAT, ["EU"], "ML_MODEL")
        assert len(res) == 1
        assert res[0]["signal_id"] == SIG_REG

    def test_domain_mismatch(self):
        assert len(match_signals_to_nodes(CAT, ["US"], "BUSINESS_RULE_SET")) == 0

    def test_affinity_mismatch(self):
        assert len(match_signals_to_nodes(CAT, ["EU"], "BUSINESS_RULE_SET")) == 0


class TestProcessRawEvents:
    def test_shock_generated_with_correct_magnitude(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        raw = [
            {
                "type": "regulatory",
                "event_id": "r4",
                "timestamp": now,
                "severity": 0.8,
                "domain_tags": ["EU"],
            }
        ]
        mem = {}
        shocks = process_raw_events(
            raw, CAT, ["EU"], "ML_MODEL", now, mem, DEBOUNCE_CFG
        )
        assert len(shocks) == 1
        # magnitude = default_magnitude(0.3) * severity(0.8) * quality(0.9) = 0.216
        assert shocks[0]["magnitude"] == pytest.approx(0.3 * 0.8 * 0.9)

    def test_debounce_filters_duplicate(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        raw1 = [
            {
                "type": "regulatory",
                "event_id": "r5",
                "timestamp": now,
                "severity": 0.5,
                "domain_tags": ["EU"],
            }
        ]
        mem = {}
        shocks1 = process_raw_events(
            raw1, CAT, ["EU"], "ML_MODEL", now, mem, DEBOUNCE_CFG
        )
        assert len(shocks1) == 1

        now2 = now + timedelta(hours=1)
        raw2 = [
            {
                "type": "regulatory",
                "event_id": "r5",
                "timestamp": now2,
                "severity": 0.5,
                "domain_tags": ["EU"],
            }
        ]
        shocks2 = process_raw_events(
            raw2, CAT, ["EU"], "ML_MODEL", now2, mem, DEBOUNCE_CFG
        )
        assert len(shocks2) == 0
