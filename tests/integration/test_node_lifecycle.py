"""Integration test: full node governance lifecycle."""
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.models.node import Base, Node, NodeClass, Criticality, NodeStatus, AuditLog
from src.core.orchestrator.pipeline import process_node_lifecycle
from src.core.signals.catalogue import create_signal

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"


@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine(TEST_DB_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_node(db_session: Session) -> Node:
    node = Node(
        node_class=NodeClass.ML_MODEL,
        version_ref="model:v1",
        owner_team="risk",
        criticality=Criticality.HIGH,
        domain_tags=["EU"],
        decay_alpha=0.01,
        registration_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    db_session.add(node)
    db_session.commit()
    return node


@pytest.fixture
def signal_catalogue(db_session):
    catalog = {}
    # Increase default_magnitude to 0.35 so that regulatory shocks are more effective
    create_signal(catalog, "REGULATORY", ["EU"], default_magnitude=0.35,
                  node_class_affinity=["ML_MODEL"])
    return catalog


class TestNodeLifecycle:
    def test_full_cycle_regulatory_shock(self, db_session, sample_node, signal_catalogue):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        raw_events = [{
            "type": "regulatory",
            "event_id": "r123",
            "timestamp": now,
            "severity": 0.8,
            "domain_tags": ["EU"],
        }]
        process_node_lifecycle(
            node_id=sample_node.node_id,
            db=db_session,
            catalogue=signal_catalogue,
            raw_events=raw_events,
            now=now,
            debounce_config={"regulatory": 24, "macroeconomic": 24, "structural": 0},
            cost_config={
                "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
                "C_err": 500.0,
                "C_int": 1000.0,
                "provisional_hazard": 0.2,
                "floor_axes": {"r": 0.2, "s": 0.1},
            },
        )
        db_session.refresh(sample_node)
        assert sample_node.r_t < 1.0
        assert sample_node.r_r < 1.0
        assert sample_node.status == NodeStatus.PROVISIONAL
        audit_entries = db_session.query(AuditLog).filter(
            AuditLog.node_id == sample_node.node_id
        ).all()
        assert len(audit_entries) >= 2

    def test_no_signals_idle(self, db_session, sample_node, signal_catalogue):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        process_node_lifecycle(
            node_id=sample_node.node_id,
            db=db_session,
            catalogue=signal_catalogue,
            raw_events=[],
            now=now,
            debounce_config={},
            cost_config={
                "weights": {"s": 0.2, "p": 0.2, "c": 0.2, "r": 0.2, "t": 0.2},
                "C_err": 10,          # low error cost to avoid escalation
                "C_int": 1000,        # high intervention cost
                "provisional_hazard": 0.9,
                "floor_axes": {"r": 0.01, "s": 0.01},
            },
        )
        db_session.refresh(sample_node)
        assert sample_node.status == NodeStatus.ACTIVE
        assert sample_node.r_t < 1.0

    def test_node_not_found_raises(self, db_session, signal_catalogue):
        with pytest.raises(ValueError, match="Node not found"):
            process_node_lifecycle(
                node_id=uuid.uuid4(),
                db=db_session,
                catalogue=signal_catalogue,
                raw_events=[],
                now=datetime.now(timezone.utc),
                debounce_config={},
                cost_config={},
            )
