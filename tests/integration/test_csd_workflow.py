"""Integration test: CSD early‑warning detection via the scheduler."""
from datetime import datetime, timezone, timedelta
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.models.node import Base, Node, NodeClass, Criticality, NodeStatus, AuditLog
from src.core.engine.csd_integration import check_and_warn_node

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"


@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


class TestCSDWorkflow:
    def test_declining_node_triggers_warning(self, db_session):
        # Create a node
        node = Node(
            node_class=NodeClass.ML_MODEL,
            version_ref="v1",
            owner_team="risk",
            criticality=Criticality.HIGH,
            domain_tags=["EU"],
            decay_alpha=0.01,
            registration_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        db_session.add(node)
        db_session.commit()

        # Insert 30 reliability snapshots showing a clear declining trend
        for i in range(30):
            # r_r declines from 1.0 down to 0.4
            r_r = 1.0 - i * 0.02
            payload = {
                "new_R": [1.0, 1.0, 1.0, r_r, 1.0],
                "hazard": 0.1,
            }
            log = AuditLog(
                node_id=node.node_id,
                event_type="reliability_updated",
                event_payload=json.dumps(payload),
            )
            db_session.add(log)
        db_session.commit()

        # Run CSD detection
        fired = check_and_warn_node(node, db_session)
        db_session.refresh(node)
        assert fired is True
        assert node.status == NodeStatus.PRE_FAILURE_WARNING

        # Verify audit log contains csd_warning
        warning_logs = (
            db_session.query(AuditLog)
            .filter(AuditLog.node_id == node.node_id, AuditLog.event_type == "csd_warning")
            .all()
        )
        assert len(warning_logs) >= 1

    def test_stable_node_no_warning(self, db_session):
        node = Node(
            node_class=NodeClass.ML_MODEL,
            version_ref="v2",
            owner_team="risk",
            criticality=Criticality.HIGH,
            domain_tags=["EU"],
            decay_alpha=0.01,
            registration_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        db_session.add(node)
        db_session.commit()

        # Insert 30 stable snapshots
        for _ in range(30):
            payload = {"new_R": [1.0, 1.0, 1.0, 1.0, 1.0], "hazard": 0.0}
            log = AuditLog(
                node_id=node.node_id,
                event_type="reliability_updated",
                event_payload=json.dumps(payload),
            )
            db_session.add(log)
        db_session.commit()

        fired = check_and_warn_node(node, db_session)
        db_session.refresh(node)
        assert fired is False
        assert node.status == NodeStatus.ACTIVE
