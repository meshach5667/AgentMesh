import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class NodeEnrollmentToken(Base):
    """Short-lived, single-use token a provider hands to a worker so it can enroll a node."""

    __tablename__ = "node_enrollment_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    name = Column(String(255), nullable=True)
    region = Column(String(100), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CommandType(str, enum.Enum):  # noqa: UP042
    DEPLOY = "DEPLOY"
    STOP = "STOP"


class CommandStatus(str, enum.Enum):  # noqa: UP042
    PENDING = "PENDING"
    LEASED = "LEASED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NodeCommand(Base):
    """Persisted command queue. Workers lease commands by polling outbound; the command id doubles as
    the idempotency key, so a redelivered command is never executed twice by a well-behaved worker."""

    __tablename__ = "node_commands"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False, index=True)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id"), nullable=True, index=True)
    type = Column(String(20), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default=CommandStatus.PENDING, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    lease_expires_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
