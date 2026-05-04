"""Mocked Temporal tests – verify workflow logic without a real server."""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.models.node import Base, Node, NodeClass, Criticality, EscalationTask
from src.core.orchestrator.escalation import create_escalation_task
from src.worker.dispatcher import dispatch_pending_tasks, approve_escalation
from src.worker.workflows import HumanReviewWorkflow

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"


@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine(TEST_DB_URL)
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


class TestMockedTemporal:
    @pytest.mark.asyncio
    async def test_dispatch_pending_tasks(self, db_session, sample_node):
        """Dispatch should start workflows for all PENDING tasks."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        task_id = create_escalation_task(
            node_id=sample_node.node_id,
            team="risk",
            reason="test",
            db=db_session,
            now=now,
            deadline_hours=24,
        )
        # Mock the Temporal client
        mock_client = AsyncMock()
        mock_client.start_workflow = AsyncMock(return_value="wf-handle-123")

        dispatched = await dispatch_pending_tasks(db_session, mock_client)
        assert dispatched == 1

        task = db_session.get(EscalationTask, task_id)
        assert task.status == "IN_PROGRESS"
        assert "workflow_id=hr-" in task.notes

    @pytest.mark.asyncio
    async def test_approve_escalation(self, db_session, sample_node):
        """Approval should signal the workflow and mark the task COMPLETED."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        task_id = create_escalation_task(
            node_id=sample_node.node_id,
            team="risk",
            reason="test",
            db=db_session,
            now=now,
            deadline_hours=24,
        )
        # Set the task to IN_PROGRESS (as if dispatch already happened)
        task = db_session.get(EscalationTask, task_id)
        task.status = "IN_PROGRESS"
        task.notes = f"workflow_id=hr-{task_id}"
        db_session.commit()

        # Mock the Temporal client
        mock_client = AsyncMock()
        mock_handle = AsyncMock()
        mock_handle.signal = AsyncMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        await approve_escalation(task_id, db_session, mock_client)
        db_session.refresh(task)
        assert task.status == "COMPLETED"


