"""
Decision Node Registry – core ORM model.

Each row holds the full reliability vector R(t) = [R_s, R_p, R_c, R_r, R_t]
and per‑node governance parameters. The derived hazard H(t) is computed
by the Reliability Engine; this model stores only the raw state.
"""
from __future__ import annotations

import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    String,
    Enum as SAEnum,
    ARRAY,
    Interval,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class NodeClass(str, PyEnum):
    """Taxonomy of decision artefacts the system governs."""
    ML_MODEL = "ML_MODEL"
    BUSINESS_RULE_SET = "BUSINESS_RULE_SET"
    API_CONTRACT = "API_CONTRACT"
    DB_SCHEMA = "DB_SCHEMA"
    SCORING_FUNCTION = "SCORING_FUNCTION"
    ETL_TRANSFORM = "ETL_TRANSFORM"


class Criticality(str, PyEnum):
    """Governance urgency tier."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    STANDARD = "STANDARD"


class NodeStatus(str, PyEnum):
    """Operational life‑cycle state."""
    ACTIVE = "ACTIVE"
    PROVISIONAL = "PROVISIONAL"      # output marked as provisional
    IN_REVIEW = "IN_REVIEW"          # human review task open
    SUSPENDED = "SUSPENDED"          # outputs blocked
    RETIRED = "RETIRED"              # node removed from service


class Node(Base):
    """
    A single decision‑producing unit (model, rule set, contract, …).

    Reliability is tracked as a 5‑axis vector:
        R_s  – structural validity
        R_p  – empirical performance
        R_c  – context alignment
        R_r  – regulatory compliance
        R_t  – temporal freshness

    All axes ∈ [0,1]; 1 = fully healthy, 0 = completely untrustworthy.
    """
    __tablename__ = "nodes"

    # ── identity & provenance ────────────────────────────────
    node_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Immutable unique identifier",
    )
    node_class = Column(
        SAEnum(NodeClass, name="node_class_t"), nullable=False,
        comment="Type of decision artefact",
    )
    version_ref = Column(
        String, nullable=False,
        comment="Pointer to artefact version (mlflow run id, git sha, schema hash, …)",
    )
    registration_time = Column(
        DateTime(timezone=True), server_default=text("now()"),
        comment="When this node version was enrolled",
    )
    last_validation_time = Column(
        DateTime(timezone=True), nullable=True,
        comment="Last human/automated recertification timestamp",
    )
    lineage_parent = Column(
        UUID(as_uuid=True), nullable=True,
        comment="Previous node version → artefact lineage (Mertens)",
    )

    # ── ownership & criticality ──────────────────────────────
    owner_team = Column(String, nullable=False)
    criticality = Column(
        SAEnum(Criticality, name="criticality_t"), nullable=False,
    )
    domain_tags = Column(
        ARRAY(String), default=[],
        comment="Tags for signal‑to‑node routing (e.g. ['credit','EU','GDPR'])",
    )

    # ── multi‑axis reliability state R(t) ─────────────────────
    r_s = Column(Float, default=1.0, comment="Structural validity (breaking changes)")
    r_p = Column(Float, default=1.0, comment="Empirical performance (drift)")
    r_c = Column(Float, default=1.0, comment="Context alignment (macro/behavioural)")
    r_r = Column(Float, default=1.0, comment="Regulatory compliance")
    r_t = Column(Float, default=1.0, comment="Temporal freshness (pure recency)")

    # ── operational meta‑state ───────────────────────────────
    status = Column(
        SAEnum(NodeStatus, name="status_t"),
        default=NodeStatus.ACTIVE,
        comment="Governance action flag",
    )
    ttl_override = Column(
        Interval, nullable=True,
        comment="Programmatic TTL pushed to Redis when confidence decays",
    )
    decay_alpha = Column(
        Float, default=0.0,
        comment="Base decay rate for temporal axis R_t (ln2 / half‑life)",
    )
    threshold_provisional = Column(
        Float, default=0.6,
        comment="Hazard threshold above which outputs become PROVISIONAL",
    )
    threshold_review = Column(
        Float, default=0.3,
        comment="Hazard threshold above which human review is triggered",
    )

    # ── convenience properties ───────────────────────────────
    @property
    def reliability_vector(self) -> tuple[float, float, float, float, float]:
        """Return the full R(t) vector for consumption by the engine."""
        return (self.r_s, self.r_p, self.r_c, self.r_r, self.r_t)

    def __repr__(self) -> str:
        return (
            f"<Node {self.node_class.value}:{self.version_ref[:8]}"
            f" status={self.status.value}"
            f" R=({self.r_s:.2f},{self.r_p:.2f},{self.r_c:.2f},"
            f"{self.r_r:.2f},{self.r_t:.2f})>"
        )