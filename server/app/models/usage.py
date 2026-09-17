import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class UsageRecord(Base):
    __tablename__ = "usage_records"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workload_id = Column(UUID(as_uuid=True), ForeignKey("workloads.id"), nullable=True)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id"))
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"))
    gpu_seconds = Column(Float, default=0)
    cpu_seconds = Column(Float, default=0)
    storage_usage = Column(Float, default=0)
    bandwidth_usage = Column(Float, default=0)
    total_cost = Column(Numeric(18, 8), default=0)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
