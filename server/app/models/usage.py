import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class UsageRecord(Base):
    """Metering record. kind="inference" rows describe one gateway request; kind="resource" rows describe
    resource consumption over a period. Prompt and response contents are never stored."""

    __tablename__ = "usage_records"
    __table_args__ = (UniqueConstraint("request_id", name="uq_usage_records_request_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workload_id = Column(UUID(as_uuid=True), ForeignKey("workloads.id"), nullable=True, index=True)
    deployment_id = Column(UUID(as_uuid=True), ForeignKey("deployments.id"), index=True)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"))
    gpu_seconds = Column(Float, default=0)
    cpu_seconds = Column(Float, default=0)
    storage_usage = Column(Float, default=0)
    bandwidth_usage = Column(Float, default=0)
    total_cost = Column(Numeric(18, 8), default=0)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    kind = Column(String(20), nullable=False, default="resource")
    # Gateway-generated request id; unique so a retried metering write cannot double count.
    request_id = Column(String(64), nullable=True)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True)
    endpoint = Column(String(100), nullable=True)
    status_code = Column(Integer, nullable=True)
    outcome = Column(String(30), nullable=True)  # success | runtime_error | cancelled | timeout | node_unavailable
    duration_ms = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    # "runtime_reported": counts come from the model runtime on a provider node and are not independently
    # verified. NULL counts mean the runtime did not report them; they are never estimated.
    token_source = Column(String(30), nullable=True)
    response_bytes = Column(Integer, nullable=True)
