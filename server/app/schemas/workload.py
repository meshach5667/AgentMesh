import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.workload import WorkloadStatus


class InferenceRequest(BaseModel):
    model: str
    input: dict[str, Any]
    requirements: dict[str, Any] = Field(default_factory=dict)


class WorkloadOut(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    node_id: uuid.UUID | None
    status: WorkloadStatus
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True

    @classmethod
    def from_workload(cls, workload):
        return cls(
            id=workload.id,
            model_id=workload.model_id,
            node_id=workload.node_id,
            status=workload.status,
            result=workload.result_data,
            error_code=workload.error_code,
            error_message=workload.error_message,
            created_at=workload.created_at,
            started_at=workload.started_at,
            completed_at=workload.completed_at,
        )
