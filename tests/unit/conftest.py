"""Skip unit tests that require PostgreSQL when the database is unavailable."""
import pytest
import socket

def _pg_is_reachable(host="localhost", port=5432):
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

@pytest.fixture(scope="session", autouse=True)
def skip_node_tests_if_no_postgres(request):
    """The node model tests need a real PostgreSQL (ARRAY/UUID types). Skip them when PG is down."""
    # Only affect test_node.py (you can extend to other files if needed)
    if "test_node" in request.node.fspath.basename:
        if not _pg_is_reachable():
            pytest.skip("PostgreSQL is not available – skipping PostgreSQL‑dependent unit tests")
