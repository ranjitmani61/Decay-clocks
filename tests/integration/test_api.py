"""Integration tests for the FastAPI REST layer."""
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.models.node import Base, Node, NodeClass, Criticality
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
    """Make the FastAPI app use the test database."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestNodeAPI:
    @pytest.mark.asyncio
    async def test_create_node(self, async_client):
        payload = {
            "node_class": "ML_MODEL",
            "version_ref": "model:v1",
            "owner_team": "risk",
            "criticality": "HIGH",
            "domain_tags": ["EU"],
            "decay_alpha": 0.01,
        }
        response = await async_client.post("/nodes", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["node_class"] == "ML_MODEL"
        assert data["reliability"]["r_t"] == 1.0   # fixed path

    @pytest.mark.asyncio
    async def test_get_node(self, async_client, db_session):
        node = Node(
            node_class=NodeClass.BUSINESS_RULE_SET,
            version_ref="rule:v1",
            owner_team="compliance",
            criticality=Criticality.STANDARD,
            domain_tags=["EU"],
        )
        db_session.add(node)
        db_session.commit()

        response = await async_client.get(f"/nodes/{node.node_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["reliability"]["r_s"] == 1.0

    @pytest.mark.asyncio
    async def test_get_node_not_found(self, async_client):
        response = await async_client.get(
            "/nodes/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_ingest_signal_and_trigger_decay(
        self, async_client, db_session
    ):
        node = Node(
            node_class=NodeClass.ML_MODEL,
            version_ref="model:v1",
            owner_team="risk",
            criticality=Criticality.HIGH,
            domain_tags=["EU"],
            decay_alpha=0.01,
            registration_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        db_session.add(node)
        db_session.commit()

        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload = {
            "raw_events": [
                {
                    "type": "regulatory",
                    "event_id": "r1",
                    "timestamp": now.isoformat(),
                    "severity": 0.8,
                    "domain_tags": ["EU"],
                }
            ]
        }
        response = await async_client.post("/signals/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["updated_nodes"]) >= 1
        db_session.refresh(node)
        assert node.r_r < 1.0
