"""Integration test: portfolio covariance from real audit‑log data."""
import json
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from src.core.models.node import Base, Node, NodeClass, Criticality, AuditLog
from src.core.engine.portfolio import (
    extract_hazard_series,
    compute_hazard_covariance_matrix,
)

TEST_DB_URL = "postgresql://dc:dcpass@localhost:5432/decay_clocks_test"


@pytest.fixture(scope="function")
def db_session() -> Session:
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


def _create_node(db: Session, name: str) -> Node:
    node = Node(
        node_class=NodeClass.ML_MODEL,
        version_ref=name,
        owner_team="risk",
        criticality=Criticality.HIGH,
        domain_tags=["EU"],
        decay_alpha=0.01,
        registration_time=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    db.add(node)
    db.commit()
    return node


def _add_hazard_events(db: Session, node: Node, hazards: list[float]):
    """Insert a reliability_updated event for each hazard value."""
    for h in hazards:
        payload = json.dumps({"new_R": [1.0, 1.0, 1.0, 1.0, 1.0], "hazard": h})
        db.add(AuditLog(node_id=node.node_id, event_type="reliability_updated", event_payload=payload))
    db.commit()


class TestPortfolioPipeline:
    def test_extract_and_covariance_symmetric(self, db_session):
        """Covariance matrix from real audit data must be symmetric and have positive diagonal."""
        # Create 3 nodes with correlated hazard histories
        node_a = _create_node(db_session, "A")
        node_b = _create_node(db_session, "B")
        node_c = _create_node(db_session, "C")

        # A and B follow similar upward trend → positive correlation
        base = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55,
                0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05]
        _add_hazard_events(db_session, node_a, [h for h in base])
        _add_hazard_events(db_session, node_b, [h * 0.9 + 0.05 for h in base])  # similar
        _add_hazard_events(db_session, node_c, [h * 0.2 + 0.4 for h in base])   # weaker correlation

        series = extract_hazard_series([str(node_a.node_id), str(node_b.node_id), str(node_c.node_id)], db_session)
        assert len(series) == 3, f"Expected 3 series, got {len(series)}"

        cov, ids = compute_hazard_covariance_matrix(series)
        assert cov.shape == (3, 3)
        # Symmetry
        assert np.allclose(cov, cov.T), "Covariance matrix must be symmetric"
        # Positive variance on diagonal
        assert all(cov[i, i] > 0 for i in range(3))

    def test_excludes_short_history(self, db_session):
        """Nodes with fewer than min_history points must be excluded."""
        node_a = _create_node(db_session, "A")
        node_b = _create_node(db_session, "B")

        _add_hazard_events(db_session, node_a, [0.1, 0.2, 0.3] * 10)  # 30 points
        _add_hazard_events(db_session, node_b, [0.1, 0.2])              # only 2 points

        series = extract_hazard_series(
            [str(node_a.node_id), str(node_b.node_id)],
            db_session,
            min_history=20,
        )
        assert str(node_a.node_id) in series
        assert str(node_b.node_id) not in series, "Node B should be excluded (short history)"

    def test_correlation_in_bounds(self, db_session):
        """All correlation coefficients must be in [-1, 1]."""
        node_a = _create_node(db_session, "A")
        node_b = _create_node(db_session, "B")
        node_c = _create_node(db_session, "C")

        # Pattern: A rising, B falling, C random
        for i in range(30):
            h_a = 0.1 + i * 0.03
            h_b = 1.0 - i * 0.03
            h_c = 0.5 + (i % 7) * 0.05
            for node, h in [(node_a, h_a), (node_b, h_b), (node_c, h_c)]:
                payload = json.dumps({"new_R": [1.0]*5, "hazard": h})
                db_session.add(AuditLog(node_id=node.node_id, event_type="reliability_updated", event_payload=payload))
        db_session.commit()

        series = extract_hazard_series(
            [str(node_a.node_id), str(node_b.node_id), str(node_c.node_id)],
            db_session,
        )
        cov, ids = compute_hazard_covariance_matrix(series)
        # Convert covariance to correlation
        std = np.sqrt(np.diag(cov))
        corr = cov / np.outer(std, std)

        assert np.all(corr >= -1.0) and np.all(corr <= 1.0), "Correlations must be in [-1, 1]"
