"""Prometheus metrics for the Decay Clocks API."""
from prometheus_client import Counter

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

STATE_TRANSITIONS = Counter(
    "decayclocks_state_transitions_total",
    "Total governance state transitions",
    ["from_status", "to_status"],
)
