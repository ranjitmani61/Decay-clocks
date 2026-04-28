"""Prometheus metrics for the Decay Clocks API."""
from prometheus_client import Counter, generate_latest, REGISTRY

REQUEST_COUNT = Counter(
    "decayclocks_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)
PIPELINE_RUNS = Counter(
    "decayclocks_pipeline_runs_total",
    "Total governance pipeline runs",
)
ESCALATION_TASKS = Counter(
    "decayclocks_escalation_tasks_total",
    "Total escalation tasks created",
)
