import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class DeploymentStatus(str, enum.Enum):  # noqa: UP042
    """Lifecycle states. Valid transitions are defined in app.services.deployment_lifecycle."""

    REQUESTED = "REQUESTED"
    SCHEDULED = "SCHEDULED"
    PROVISIONING = "PROVISIONING"
    STARTING = "STARTING"
    READY = "READY"
    UNHEALTHY = "UNHEALTHY"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (UniqueConstraint("customer_id", "idempotency_key", name="uq_deployments_customer_idempotency"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"))
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"))
    status = Column(String(50), default=DeploymentStatus.REQUESTED, index=True)
    endpoint = Column(String(500), nullable=True)
    config = Column(JSON)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    runtime = Column(String(50), nullable=True)
    model_tag = Column(String(255), nullable=True)
    model_digest = Column(String(255), nullable=True)  # reported by the worker after pulling, for reproducibility
    idempotency_key = Column(String(128), nullable=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    ready_at = Column(DateTime, nullable=True)
    last_health_at = Column(DateTime, nullable=True)
    was_ready = Column(Boolean, nullable=False, default=False)
    cleanup_status = Column(String(50), nullable=True)  # pending | done | pending_node
    deleted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DeploymentEvent(Base):
    """Append-only lifecycle history, shown to customers for progress and troubleshooting."""

    __tablename__ = "deployment_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id", ondelete="CASCADE"), index=True)
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=True)
    actor = Column(String(50), nullable=False)  # customer | worker | system | operator
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
