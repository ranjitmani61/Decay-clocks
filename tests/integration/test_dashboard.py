import pytest
from httpx import AsyncClient, ASGITransport
from src.core.api.main import app, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.core.models.node import Base

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"

@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(autouse=True)
def override_db(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_dashboard_loads():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/dashboard")
        assert resp.status_code == 200
        assert "DECAY CLOCKS" in resp.text
