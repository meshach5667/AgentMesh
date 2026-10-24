import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, index


class WorkloadStatus(str, enum.Enum):  # noqa: UP042
    QUEUED = "QUEUED"
    SCHEDULING = "SCHEDULING"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class Workload(Doc):
    """Legacy one-shot inference record (pre-gateway). Kept for history."""

    customer_id: uuid.UUID
    model_id: uuid.UUID
    node_id: uuid.UUID | None = None
    status: WorkloadStatus = WorkloadStatus.QUEUED
    input_data: Any
    result_data: Any = None
    error_code: str | None = None
    error_message: str | None = None
    tokens_in: int | None = 0
    tokens_out: int | None = 0
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "workloads"
        indexes = [index("customer_id"), index("status")]
