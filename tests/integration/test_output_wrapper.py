"""Integration test: Output Wrapper annotates decisions with provenance."""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.models.node import Base, Node, NodeClass, Criticality, NodeStatus
from src.core.output.wrapper import wrap_decision

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"


@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine(TEST_DB_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_node(db_session: Session) -> Node:
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
    return node


class TestWrapDecision:
    def test_active_node_returns_provenance_without_provisional(
        self, db_session, sample_node
    ):
        decision = {"score": 0.85, "approved": True}
        wrapped = wrap_decision(
            node_id=sample_node.node_id,
            original_output=decision,
            db=db_session,
        )
        assert wrapped["__provenance__"]["node_id"] == str(sample_node.node_id)
        assert wrapped["__provenance__"]["provisional"] is False
        assert wrapped["score"] == 0.85  # original preserved

    def test_provisional_node_flags_provisional_true(
        self, db_session, sample_node
    ):
        # Force node into provisional state
        sample_node.status = NodeStatus.PROVISIONAL
        db_session.commit()
        decision = {"score": 0.5}
        wrapped = wrap_decision(
            node_id=sample_node.node_id,
            original_output=decision,
            db=db_session,
        )
        assert wrapped["__provenance__"]["provisional"] is True

    def test_invalid_node_raises(self, db_session):
        with pytest.raises(ValueError, match="Node not found"):
            wrap_decision(
                node_id="00000000-0000-0000-0000-000000000000",
                original_output={},
                db=db_session,
            )
