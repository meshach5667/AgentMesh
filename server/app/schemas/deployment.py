import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.deployment import DeploymentStatus


class DeploymentCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_id: uuid.UUID
    config: dict[str, Any] = Field(default_factory=dict, description="num_ctx, region, require_gpu")
    idempotency_key: str | None = Field(
        None, max_length=128, description="Retries with the same key return the same deployment"
    )


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: uuid.UUID
    customer_id: uuid.UUID
    model_id: uuid.UUID
    node_id: uuid.UUID | None
    status: DeploymentStatus
    endpoint: str | None
    runtime: str | None = None
    model_tag: str | None = None
    model_digest: str | None = None
    config: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    ready_at: datetime | None = None
    ended_at: datetime | None = None
    cleanup_status: str | None = None


class DeploymentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    from_status: str | None
    to_status: str | None
    actor: str
    message: str | None
    created_at: datetime
