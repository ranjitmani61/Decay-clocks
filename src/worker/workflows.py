"""Temporal workflow for human review escalation."""
from temporalio import workflow

@workflow.defn
class HumanReviewWorkflow:
    """Wait for human approval signal."""
    def __init__(self):
        self._approved = False
        self._result = ""

    @workflow.run
    async def run(self, task_id: str, reason: str) -> str:
        await workflow.wait_condition(lambda: self._approved)
        return f"approved-{task_id}"

    @workflow.signal
    async def approve(self):
        self._approved = True
