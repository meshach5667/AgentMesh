import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import ZERO, Doc, Money, index, unique


class NodeStatus(str, enum.Enum):  # noqa: UP042
    REGISTERING = "REGISTERING"
    ONLINE = "ONLINE"
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    SUSPENDED = "SUSPENDED"
    QUARANTINED = "QUARANTINED"  # cut off by an operator pending investigation; reversible
    REVOKED = "REVOKED"


# A node in one of these states cannot authenticate, keep a tunnel open, or receive work.
BLOCKED_NODE_STATUSES = frozenset({NodeStatus.SUSPENDED.value, NodeStatus.QUARANTINED.value, NodeStatus.REVOKED.value})


class Node(Doc):
    owner_id: uuid.UUID
    name: str | None = None
    public_key: str | None = None
    api_key_hash: str | None = None
    status: str | None = NodeStatus.REGISTERING.value
    region: str | None = None
    last_heartbeat: datetime | None = None
    reputation_score: Money | None = Decimal("100.00")
    created_at: datetime | None = Field(default_factory=utcnow)
    updated_at: datetime | None = Field(default_factory=utcnow)

    # Worker identity and protocol
    mode: str | None = None
    worker_version: str | None = None
    protocol_version: int | None = None
    runtimes: Any = None  # [{"name": "ollama", "backend": ..., ...}]
    # Set by the provider in the dashboard (pause/resume).
    accepting_workloads: bool = True
    # Provider opt-in to unreviewed community models imported by customers. Off unless the provider turns it on.
    accepts_community_models: bool = False
    # Reported by the worker itself: local pause/drain or outside its availability schedule.
    worker_available: bool = True
    worker_unavailable_reason: str | None = None
    last_metrics: Any = None
    quarantined_at: datetime | None = None
    quarantine_reason: str | None = None

    # Capacity the provider has explicitly allocated to AgentMesh (never the whole machine by default),
    # and capacity currently reserved by deployments. Reservations are changed only with atomic
    # conditional updates in app.services.scheduler_service.
    allocated_cpu_cores: int = 0
    allocated_ram_mb: int = 0
    allocated_disk_mb: int = 0
    allocated_vram_mb: int = 0
    reserved_cpu_cores: int = 0
    reserved_ram_mb: int = 0
    reserved_disk_mb: int = 0
    reserved_vram_mb: int = 0

    class Settings(Doc.Settings):
        name = "nodes"
        indexes = [index("owner_id"), index("status"), index("api_key_hash")]


class NodeHardware(Doc):
    node_id: uuid.UUID
    cpu_model: str | None = None
    cpu_cores: int | None = None
    ram_gb: int | None = None
    storage_gb: int | None = None
    gpu_model: str | None = None
    gpu_count: int | None = 0
    gpu_vram_gb: int | None = None
    os_info: str | None = None
    capabilities: Any = None

    class Settings(Doc.Settings):
        name = "node_hardware"
        indexes = [unique("node_id", name="uq_node_hardware_node_id")]


class PricingMode(str, enum.Enum):  # noqa: UP042
    PROVIDER_FIXED = "PROVIDER_FIXED"
    AGENTMESH_RECOMMENDED = "AGENTMESH_RECOMMENDED"


class NodePricing(Doc):
    node_id: uuid.UUID
    gpu_hour_price: Money | None = ZERO
    cpu_hour_price: Money | None = ZERO
    ram_gb_hour_price: Money | None = ZERO
    storage_gb_month_price: Money | None = ZERO
    bandwidth_gb_price: Money | None = ZERO
    pricing_mode: str | None = PricingMode.PROVIDER_FIXED.value
    currency: str | None = "USD"

    class Settings(Doc.Settings):
        name = "node_pricing"
        indexes = [unique("node_id", name="uq_node_pricing_node_id")]
