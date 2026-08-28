import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.deployment import DeploymentStatus


class DeploymentCreate(BaseModel):
    model_id: uuid.UUID
    config: dict[str, Any]


class DeploymentOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    model_id: uuid.UUID
    node_id: uuid.UUID | None
    status: DeploymentStatus
    endpoint: str | None
    created_at: datetime

    class Config:
        from_attributes = True
