import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ResourceReservation(Base):
    """Capacity held on a node for one deployment. At most one per deployment."""

    __tablename__ = "resource_reservations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id"), nullable=False, unique=True)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False, index=True)
    cpu_cores = Column(Integer, nullable=False, default=0)
    ram_mb = Column(Integer, nullable=False, default=0)
    disk_mb = Column(Integer, nullable=False, default=0)
    vram_mb = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="ACTIVE")  # ACTIVE | RELEASED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    released_at = Column(DateTime, nullable=True)
