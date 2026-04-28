"""Temporal client helpers: start workflows, approve tasks."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from temporalio.client import Client

from src.core.models.node import EscalationTask
from src.worker.workflows import HumanReviewWorkflow

TASK_QUEUE = "decay-clocks-queue"

async def dispatch_pending_tasks(db: Session, client: Client) -> int:
    """Start Temporal workflows for all PENDING escalation tasks.
    Returns number of tasks dispatched.
    """
    tasks = db.query(EscalationTask).filter_by(status="PENDING").all()
    count = 0
    for task in tasks:
        workflow_id = f"hr-{task.id}"
        try:
            await client.start_workflow(
                HumanReviewWorkflow.run,
                args=[str(task.id), task.notes or ""],
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            task.status = "IN_PROGRESS"
            task.notes = f"workflow_id={workflow_id}"
            db.commit()
            count += 1
        except Exception:
            # Workflow already exists or other error; skip
            db.rollback()
    return count


async def approve_escalation(task_id: uuid.UUID, db: Session, client: Client) -> None:
    """Approve an escalation task: signal workflow, mark COMPLETED."""
    task = db.get(EscalationTask, task_id)
    if not task or task.status != "IN_PROGRESS":
        raise ValueError("Task not in progress")
    # Extract workflow ID from notes
    wf_id = task.notes.replace("workflow_id=", "").strip()
    handle = client.get_workflow_handle(wf_id)
    await handle.signal(HumanReviewWorkflow.approve)
    # Wait for workflow to complete (optional, but ensures state)
    # Actually we can just update status
    task.status = "COMPLETED"
    task.notes = f"approved at {datetime.now(timezone.utc).isoformat()}"
    db.commit()
