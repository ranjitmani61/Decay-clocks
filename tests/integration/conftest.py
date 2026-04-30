"""Skip all integration tests when PostgreSQL is not available."""
import pytest
import socket

def _pg_is_reachable(host: str = "localhost", port: int = 5432) -> bool:
    """Return True if a TCP connection to PostgreSQL succeeds."""
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

# This fixture runs once per session and skips all integration tests if PG is absent.
@pytest.fixture(scope="session", autouse=True)
def skip_if_no_postgres():
    if not _pg_is_reachable():
        pytest.skip("PostgreSQL is not available – skipping integration tests")
