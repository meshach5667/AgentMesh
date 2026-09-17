import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class NodeStatus(str, enum.Enum):  # noqa: UP042
    REGISTERING = "REGISTERING"
    ONLINE = "ONLINE"
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    SUSPENDED = "SUSPENDED"


class Node(Base):
    __tablename__ = "nodes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)
    name = Column(String(255))
    public_key = Column(Text)
    api_key_hash = Column(String(255))
    status = Column(Enum(NodeStatus), default=NodeStatus.REGISTERING)
    region = Column(String(100))
    last_heartbeat = Column(DateTime)
    reputation_score = Column(Numeric(5, 2), default=100.00)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("Provider", back_populates="nodes")
    hardware = relationship("NodeHardware", back_populates="node", uselist=False)
    pricing = relationship("NodePricing", back_populates="node", uselist=False)


class NodeHardware(Base):
    __tablename__ = "node_hardware"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), unique=True, nullable=False)
    cpu_model = Column(String(255))
    cpu_cores = Column(Integer)
    ram_gb = Column(Integer)
    storage_gb = Column(Integer)
    gpu_model = Column(String(255), nullable=True)
    gpu_count = Column(Integer, default=0)
    gpu_vram_gb = Column(Integer, nullable=True)
    os_info = Column(String(255))
    capabilities = Column(JSON)

    node = relationship("Node", back_populates="hardware")


class PricingMode(str, enum.Enum):  # noqa: UP042
    PROVIDER_FIXED = "PROVIDER_FIXED"
    AGENTMESH_RECOMMENDED = "AGENTMESH_RECOMMENDED"


class NodePricing(Base):
    __tablename__ = "node_pricing"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), unique=True, nullable=False)
    gpu_hour_price = Column(Numeric(10, 4), default=0)
    cpu_hour_price = Column(Numeric(10, 4), default=0)
    ram_gb_hour_price = Column(Numeric(10, 6), default=0)
    storage_gb_month_price = Column(Numeric(10, 4), default=0)
    bandwidth_gb_price = Column(Numeric(10, 4), default=0)
    pricing_mode = Column(Enum(PricingMode), default=PricingMode.PROVIDER_FIXED)
    currency = Column(String(10), default="USD")

    node = relationship("Node", back_populates="pricing")
