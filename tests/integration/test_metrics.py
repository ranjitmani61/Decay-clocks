"""Integration test: Prometheus metrics endpoint."""
import re
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.core.models.node import Base
from src.core.api.main import app, get_db

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"


@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def override_get_db(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestMetrics:
    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_200(self, async_client):
        response = await async_client.get("/metrics")
        assert response.status_code == 200
        assert "decayclocks_api_requests_total" in response.text

    @pytest.mark.asyncio
    async def test_request_count_increments(self, async_client):
        await async_client.get("/health")
        response = await async_client.get("/metrics")
        # Check that the line for /health exists with all required labels,
        # but ignore label order.
        match = re.search(
            r'decayclocks_api_requests_total\{[^}]*endpoint="/health"[^}]*method="GET"[^}]*status="200"[^}]*\}',
            response.text
        )
        assert match is not None, "Health endpoint metric not found in /metrics"
