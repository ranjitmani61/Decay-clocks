"""Integration tests for the escalation dispatcher."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.models.node import Base, Node, NodeClass, Criticality, EscalationTask
from src.core.orchestrator.escalation import create_escalation_task

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
        version_ref="v1",
        owner_team="risk",
        criticality=Criticality.HIGH,
        registration_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    db_session.add(node)
    db_session.commit()
    return node


class TestCreateEscalationTask:
    def test_task_created_with_correct_deadline(self, db_session, sample_node):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        task_id = create_escalation_task(
            node_id=sample_node.node_id,
            team="risk",
            reason="Regulatory axis floor breach",
            db=db_session,
            now=now,
            deadline_hours=24,
        )
        task = db_session.get(EscalationTask, task_id)
        assert task is not None
        assert task.node_id == sample_node.node_id
        assert task.status == "PENDING"
        expected_deadline = now + timedelta(hours=24)
        assert abs((task.deadline - expected_deadline).total_seconds()) < 1

    def test_node_not_found_raises(self, db_session):
        with pytest.raises(ValueError, match="Node not found"):
            create_escalation_task(
                node_id="00000000-0000-0000-0000-000000000000",
                team="risk",
                reason="test",
                db=db_session,
                now=datetime.now(timezone.utc),
                deadline_hours=24,
            )
