"""Tests for the Node ORM model. Skip if PostgreSQL is not available."""
import pytest
import socket

def _pg_is_reachable(host="localhost", port=5432):
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except (OSError, socket.timeout):
        return False

pytestmark = pytest.mark.skipif(
    not _pg_is_reachable(),
    reason="PostgreSQL is not available – skipping Node model tests"
)

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.core.models.node import Base, Node, NodeClass, Criticality, NodeStatus

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"

@pytest.fixture(scope="function")
def session() -> Session:
    engine = create_engine(TEST_DB_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)

def test_create_minimal_node(session: Session) -> None:
    node = Node(
        node_class=NodeClass.ML_MODEL,
        version_ref="mlflow://run/abc123",
        owner_team="credit-risk",
        criticality=Criticality.HIGH,
    )
    session.add(node)
    session.commit()
    fetched = session.get(Node, node.node_id)
    assert fetched is not None
    assert fetched.node_class == NodeClass.ML_MODEL
    assert fetched.status == NodeStatus.ACTIVE
    assert fetched.r_s == 1.0
    assert fetched.r_p == 1.0
    assert fetched.r_c == 1.0
    assert fetched.r_r == 1.0
    assert fetched.r_t == 1.0
    assert fetched.decay_alpha == 0.0

def test_reliability_vector_property(session: Session) -> None:
    node = Node(
        node_class=NodeClass.BUSINESS_RULE_SET,
        version_ref="git://sha/def456",
        owner_team="compliance",
        criticality=Criticality.CRITICAL,
        r_s=0.9, r_p=0.8, r_c=0.7, r_r=0.6, r_t=0.5,
    )
    session.add(node)
    session.commit()
    fetched = session.get(Node, node.node_id)
    assert fetched.reliability_vector == (0.9, 0.8, 0.7, 0.6, 0.5)

def test_update_axis_triggered_by_engine(session: Session) -> None:
    node = Node(
        node_class=NodeClass.SCORING_FUNCTION,
        version_ref="1.3.0",
        owner_team="acquisition",
        criticality=Criticality.STANDARD,
    )
    session.add(node)
    session.commit()
    fetched = session.get(Node, node.node_id)
    fetched.r_p = 0.42
    fetched.status = NodeStatus.PROVISIONAL
    session.commit()
    refreshed = session.get(Node, node.node_id)
    assert refreshed.r_p == 0.42
    assert refreshed.status == NodeStatus.PROVISIONAL

def test_enforce_non_null_enums(session: Session) -> None:
    node = Node(
        node_class="impossible",
        version_ref="v1",
        owner_team="test",
        criticality=Criticality.STANDARD,
    )
    session.add(node)
    with pytest.raises(Exception):
        session.commit()
