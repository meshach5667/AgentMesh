import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class DeploymentStatus(str, enum.Enum):  # noqa: UP042
    REQUESTED = "REQUESTED"
    VALIDATING = "VALIDATING"
    SCHEDULING = "SCHEDULING"
    ASSIGNED = "ASSIGNED"
    DEPLOYING = "DEPLOYING"
    HEALTH_CHECK = "HEALTH_CHECK"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class Deployment(Base):
    __tablename__ = "deployments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"))
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"))
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"))
    status = Column(Enum(DeploymentStatus), default=DeploymentStatus.REQUESTED)
    endpoint = Column(String(500), nullable=True)
    config = Column(JSON)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
