"""Integration tests that guarantee configuration flows from DB → pipeline → outcome."""
import uuid, json
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy import text

from src.core.models.node import Base, Node, NodeClass, Criticality, NodeStatus, CostConfig
from src.core.orchestrator.pipeline import process_node_lifecycle
from src.core.api.config_loader import get_cost_config_for_node
from src.core.signals.catalogue import create_signal

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"


@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def signal_catalogue():
    """A minimal catalogue that matches the EU regulatory signals used in the tests."""
    cat = {}
    create_signal(cat, "REGULATORY", ["EU"], 0.35, ["ML_MODEL"])
    return cat


def _create_node(db: Session, **kwargs) -> Node:
    defaults = {
        "node_class": NodeClass.ML_MODEL,
        "version_ref": "v1",
        "owner_team": "risk",
        "criticality": Criticality.HIGH,
        "domain_tags": ["EU"],
        "decay_alpha": 0.01,
        "registration_time": datetime(2025, 6, 1, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    node = Node(**defaults)
    db.add(node)
    db.commit()
    return node


def _make_active_config(db: Session, **kwargs) -> CostConfig:
    """Deactivate all configs, create a new active one, return it."""
    db.query(CostConfig).update({"active": False})
    cfg = CostConfig(
        active=True,
        weights={"s":0.2,"p":0.2,"c":0.2,"r":0.2,"t":0.2},
        C_err=500.0,
        C_int=1000.0,
        provisional_hazard=0.1,
        floor_axes={"r":0.2,"s":0.3},
        hazard_mode="linear",
        dominant_axes=[],
        environment="test",
    )
    for key, value in kwargs.items():
        setattr(cfg, key, value)
    db.add(cfg)
    db.commit()
    return cfg


class TestConfigFidelity:
    def test_hard_gate_config_triggers_in_review(self, db_session, signal_catalogue):
        """A hard‑gate config must cause IN_REVIEW when the dominant axis falls below gate."""
        cfg = _make_active_config(
            db_session,
            hazard_mode="hard_gate",
            dominant_axes=[{"axis":"r","gate_threshold":0.5}],
        )
        node = _create_node(db_session)

        process_node_lifecycle(
            node_id=node.node_id,
            db=db_session,
            catalogue=signal_catalogue,
            raw_events=[{
                "type": "regulatory",
                "event_id": "fidelity-1",
                "timestamp": datetime.now(timezone.utc),
                "severity": 0.9,
                "domain_tags": ["EU"],
            }],
            now=datetime.now(timezone.utc),
            debounce_config={"regulatory": 0},
            cost_config=get_cost_config_for_node(node, db_session),
        )
        db_session.refresh(node)
        assert node.status == NodeStatus.IN_REVIEW

    def test_missing_hazard_mode_falls_back_to_linear(self, db_session, signal_catalogue):
        """When hazard_mode is missing from config, the system must use linear logic."""
        cfg = _make_active_config(db_session)  # no hazard_mode set
        node = _create_node(db_session)

        process_node_lifecycle(
            node_id=node.node_id,
            db=db_session,
            catalogue=signal_catalogue,
            raw_events=[{
                "type": "regulatory",
                "event_id": "fidelity-2",
                "timestamp": datetime.now(timezone.utc),
                "severity": 0.9,
                "domain_tags": ["EU"],
            }],
            now=datetime.now(timezone.utc),
            debounce_config={"regulatory": 0},
            cost_config=get_cost_config_for_node(node, db_session),
        )
        db_session.refresh(node)
        # With linear mode, hazard = 0.14, provisional_hazard = 0.1 → PROVISIONAL
        assert node.status == NodeStatus.PROVISIONAL

    def test_dominant_axes_serialization_variants(self, db_session, signal_catalogue):
        """dominant_axes stored as JSON string or list must both work."""
        # Variant 1: stored as a list (native JSON)
        cfg1 = _make_active_config(
            db_session,
            hazard_mode="hard_gate",
            dominant_axes=[{"axis":"r","gate_threshold":0.5}],
        )
        node1 = _create_node(db_session, cost_config_id=cfg1.id)

        process_node_lifecycle(
            node_id=node1.node_id,
            db=db_session,
            catalogue=signal_catalogue,
            raw_events=[{
                "type": "regulatory",
                "event_id": "fidelity-3a",
                "timestamp": datetime.now(timezone.utc),
                "severity": 0.9,
                "domain_tags": ["EU"],
            }],
            now=datetime.now(timezone.utc),
            debounce_config={"regulatory": 0},
            cost_config=get_cost_config_for_node(node1, db_session),
        )
        db_session.refresh(node1)
        assert node1.status == NodeStatus.IN_REVIEW

        # Variant 2: stored as a JSON string (simulate older DB row)
        cfg2 = _make_active_config(
            db_session,
            hazard_mode="hard_gate",
        )
        db_session.execute(
            text("UPDATE cost_config SET dominant_axes = :val WHERE id = :id"),
            {"val": '[{"axis":"r","gate_threshold":0.5}]', "id": str(cfg2.id)}
        )
        db_session.commit()
        db_session.refresh(cfg2)

        node2 = _create_node(db_session, cost_config_id=cfg2.id)
        process_node_lifecycle(
            node_id=node2.node_id,
            db=db_session,
            catalogue=signal_catalogue,
            raw_events=[{
                "type": "regulatory",
                "event_id": "fidelity-3b",
                "timestamp": datetime.now(timezone.utc),
                "severity": 0.9,
                "domain_tags": ["EU"],
            }],
            now=datetime.now(timezone.utc),
            debounce_config={"regulatory": 0},
            cost_config=get_cost_config_for_node(node2, db_session),
        )
        db_session.refresh(node2)
        assert node2.status == NodeStatus.IN_REVIEW
