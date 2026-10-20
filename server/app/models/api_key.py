import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ApiKey(Base):
    """Customer API key for the inference gateway. Only a SHA-256 hash of the secret is stored."""

    __tablename__ = "api_keys"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    prefix = Column(String(20), nullable=False)
    key_hash = Column(String(128), nullable=False, unique=True)
    scopes = Column(JSON, nullable=False)
    # Optional restriction to a single deployment. NULL means all of the user's deployments.
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
