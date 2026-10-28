import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, Money, index, unique


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
    # Health. Heartbeats carry the worker's boot id and a sequence number; one older than the last applied is
    # ignored, so a delayed heartbeat cannot overwrite newer state.
    heartbeat_boot_id: str | None = None
    heartbeat_seq: int | None = None
    # Consecutive heartbeats since the node last came back from OFFLINE; it gets new work again only after
    # NODE_RECOVERY_HEARTBEATS of them. Enrollment counts as a full check.
    recovery_heartbeats: int = 0
    # Set once by the monitor when heartbeats are late (no new work), cleared by the next heartbeat.
    heartbeat_late_at: datetime | None = None
    # Placements on this node that failed in a row (failures caused by the node); at NODE_FAILURE_THRESHOLD it is
    # kept out of scheduling until degraded_until.
    consecutive_failures: int = 0
    degraded_until: datetime | None = None

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
