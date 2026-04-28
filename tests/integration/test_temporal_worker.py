"""Integration test: Temporal workflow for human review."""
import asyncio
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from temporalio.client import Client
from temporalio.worker import Worker

from src.core.models.node import Base, Node, NodeClass, Criticality, EscalationTask
from src.core.orchestrator.escalation import create_escalation_task
from src.worker.dispatcher import dispatch_pending_tasks, approve_escalation
from src.worker.workflows import HumanReviewWorkflow

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"
TEMPORAL_HOST = "localhost:7233"
TASK_QUEUE = "decay-clocks-queue"


@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine(TEST_DB_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
async def temporal_client():
    return await Client.connect(TEMPORAL_HOST)


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


@pytest.mark.asyncio
class TestTemporalEscalation:
    async def test_dispatch_and_approve_escalation(
        self, db_session, sample_node, temporal_client
    ):
        # Start a worker for this test
        worker = Worker(
            temporal_client,
            task_queue=TASK_QUEUE,
            workflows=[HumanReviewWorkflow],
        )
        worker_task = asyncio.create_task(worker.run())

        try:
            now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            task_id = create_escalation_task(
                node_id=sample_node.node_id,
                team="risk",
                reason="regulatory floor breach",
                db=db_session,
                now=now,
                deadline_hours=24,
            )

            dispatched = await dispatch_pending_tasks(db_session, temporal_client)
            assert dispatched == 1
            task = db_session.get(EscalationTask, task_id)
            assert task.status == "IN_PROGRESS"

            await approve_escalation(task_id, db_session, temporal_client)
            db_session.refresh(task)
            assert task.status == "COMPLETED"
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
