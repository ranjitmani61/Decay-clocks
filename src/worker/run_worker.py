"""Standalone Temporal worker process."""
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from src.worker.workflows import HumanReviewWorkflow

TASK_QUEUE = "decay-clocks-queue"
TEMPORAL_HOST = "temporal:7233"

async def main():
    client = await Client.connect(TEMPORAL_HOST)
    worker = Worker(client, task_queue=TASK_QUEUE, workflows=[HumanReviewWorkflow])
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
