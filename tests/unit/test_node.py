import pytest
from sqlalchemy.orm import Session
from src.core.models.node import Node, NodeClass, Criticality, NodeStatus

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
    assert fetched.threshold_provisional == 0.6
    assert fetched.threshold_review == 0.3
    assert fetched.domain_tags == []
    assert fetched.lineage_parent is None

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
