import uuid
from datetime import datetime

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import ZERO, Doc, Money, index, unique


class UsageRecord(Doc):
    """Metering record. kind="inference" documents describe one gateway request; kind="resource" ones describe
    resource consumption over a period. Prompt and response contents are never stored."""

    workload_id: uuid.UUID | None = None
    deployment_id: uuid.UUID | None = None
    node_id: uuid.UUID | None = None
    gpu_seconds: float | None = 0
    cpu_seconds: float | None = 0
    storage_usage: float | None = 0
    bandwidth_usage: float | None = 0
    total_cost: Money | None = ZERO
    period_start: datetime | None = None
    period_end: datetime | None = None
    created_at: datetime | None = Field(default_factory=utcnow)
    kind: str = "resource"
    # Gateway-generated request id; unique so a retried metering write cannot double count.
    request_id: str | None = None
    api_key_id: uuid.UUID | None = None
    endpoint: str | None = None
    status_code: int | None = None
    outcome: str | None = None  # success | runtime_error | cancelled | timeout | ...
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    # "runtime_reported": counts come from the model runtime on a provider node and are not independently
    # verified. None means the runtime did not report them; they are never estimated.
    token_source: str | None = None
    response_bytes: int | None = None

    class Settings(Doc.Settings):
        name = "usage_records"
        indexes = [
            unique("request_id", name="uq_usage_records_request_id", nullable=("request_id",)),
            index("workload_id"),
            index("deployment_id", "created_at"),
        ]
