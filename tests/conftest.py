import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.core.models.node import Base

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"

@pytest.fixture(scope="function")
def session() -> Session:
    engine = create_engine(TEST_DB_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
