from pydantic import BaseModel
from decimal import Decimal
from typing import Optional
import uuid
from datetime import datetime

class UsageRecordResponse(BaseModel):
    id: uuid.UUID
    deployment_id: uuid.UUID
    node_id: uuid.UUID
    gpu_seconds: float
    cpu_seconds: float
    storage_usage: float
    bandwidth_usage: float
    total_cost: Decimal
    period_start: datetime
    period_end: datetime
    created_at: datetime
    model_config = {"from_attributes": True}

class UsageCreateRequest(BaseModel):
    deployment_id: uuid.UUID
    gpu_seconds: float = 0
    cpu_seconds: float = 0
    storage_usage: float = 0
    bandwidth_usage: float = 0
    period_start: datetime
    period_end: datetime

class UsageSummaryResponse(BaseModel):
    total_gpu_hours: float
    total_cpu_hours: float
    total_cost: Decimal
    record_count: int
