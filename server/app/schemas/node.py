import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NodeOut(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str | None = None
    status: str
    region: str | None = None
    reputation_score: float | None = None
    last_heartbeat: datetime | None = None
    created_at: datetime
    mode: str | None = None
    worker_version: str | None = None
    protocol_version: int | None = None
    runtimes: list[dict[str, Any]] | None = None
    accepting_workloads: bool = True
    accepts_community_models: bool = False
    worker_available: bool = True
    worker_unavailable_reason: str | None = None
    allocated_cpu_cores: int = 0
    allocated_ram_mb: int = 0
    allocated_disk_mb: int = 0
    allocated_vram_mb: int = 0
    reserved_cpu_cores: int = 0
    reserved_ram_mb: int = 0
    reserved_disk_mb: int = 0
    reserved_vram_mb: int = 0
    last_metrics: dict[str, float] | None = None
    quarantined_at: datetime | None = None
    quarantine_reason: str | None = None
    degraded_until: datetime | None = None
    consecutive_failures: int = 0
    recovery_heartbeats: int = 0
    # Derived from health evidence (heartbeat age, recovery, failure cooldown, pause, reservations):
    # ACTIVE, BUSY, DEGRADED, DRAINING, OFFLINE, or the operator's SUSPENDED / QUARANTINED / REVOKED.
    health: str | None = None
    # Whether the scheduler may place new work on it right now.
    schedulable: bool = False

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="wrap")
    @classmethod
    def _health(cls, data: Any, handler):
        from app.documents.node import Node
        from app.services.scheduler_service import health_state, schedulable

        out = handler(data)
        if isinstance(data, Node):
            out.health = health_state(data)
            out.schedulable = schedulable(data)
        return out


class EnrollmentTokenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, max_length=100)
    region: str | None = Field(None, max_length=100)


class EnrollmentTokenOut(BaseModel):
    token: str
    expires_at: datetime


class NodeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accepting_workloads: bool | None = None
    accepts_community_models: bool | None = Field(
        None, description="Allow unreviewed models that customers imported from Hugging Face on this node"
    )


class NodeHardwareUpdate(BaseModel):
    cpu_model: str
    cpu_cores: int
    ram_gb: int
    storage_gb: int
    gpu_model: str | None = None
    gpu_count: int = 0
    gpu_vram_gb: int | None = None
    os_info: str
    capabilities: dict[str, Any]


class NodeCreate(BaseModel):
    name: str
    public_key: str
    region: str
    hardware: NodeHardwareUpdate | None = None
