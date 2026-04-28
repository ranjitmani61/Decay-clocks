"""Decision Node Registry – core ORM models."""
from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column, DateTime, Float, String, Enum as SAEnum,
    ARRAY, Interval, text, JSON, ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class NodeClass(str, PyEnum):
    ML_MODEL = "ML_MODEL"
    BUSINESS_RULE_SET = "BUSINESS_RULE_SET"
    API_CONTRACT = "API_CONTRACT"
    DB_SCHEMA = "DB_SCHEMA"
    SCORING_FUNCTION = "SCORING_FUNCTION"
    ETL_TRANSFORM = "ETL_TRANSFORM"


class Criticality(str, PyEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    STANDARD = "STANDARD"


class NodeStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    PROVISIONAL = "PROVISIONAL"
    IN_REVIEW = "IN_REVIEW"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


class Node(Base):
    __tablename__ = "nodes"

    node_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_class = Column(SAEnum(NodeClass, name="node_class_t"), nullable=False)
    version_ref = Column(String, nullable=False)
    registration_time = Column(DateTime(timezone=True), server_default=text("now()"))
    last_validation_time = Column(DateTime(timezone=True), nullable=True)
    lineage_parent = Column(UUID(as_uuid=True), nullable=True)
    owner_team = Column(String, nullable=False)
    criticality = Column(SAEnum(Criticality, name="criticality_t"), nullable=False)
    domain_tags = Column(ARRAY(String), default=[])
    r_s = Column(Float, default=1.0)
    r_p = Column(Float, default=1.0)
    r_c = Column(Float, default=1.0)
    r_r = Column(Float, default=1.0)
    r_t = Column(Float, default=1.0)
    status = Column(SAEnum(NodeStatus, name="status_t"), default=NodeStatus.ACTIVE)
    ttl_override = Column(Interval, nullable=True)
    decay_alpha = Column(Float, default=0.0)
    threshold_provisional = Column(Float, default=0.6)
    threshold_review = Column(Float, default=0.3)

    @property
    def reliability_vector(self) -> tuple[float, float, float, float, float]:
        return (self.r_s, self.r_p, self.r_c, self.r_r, self.r_t)

    def __repr__(self) -> str:
        return (
            f"<Node {self.node_class.value}:{self.version_ref[:8]}"
            f" status={self.status.value}"
            f" R=({self.r_s:.2f},{self.r_p:.2f},{self.r_c:.2f},"
            f"{self.r_r:.2f},{self.r_t:.2f})>"
        )


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.node_id"), nullable=False)
    event_type = Column(String, nullable=False)
    event_payload = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class EscalationTask(Base):
    __tablename__ = "escalation_tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.node_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    deadline = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="PENDING")
    assigned_team = Column(String)
    notes = Column(String, nullable=True)
