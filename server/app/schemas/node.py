import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class NodeCreate(BaseModel):
    name: str
    public_key: str
    region: str


class NodeOut(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    status: str
    region: str
    reputation_score: float
    created_at: datetime

    class Config:
        from_attributes = True


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


class NodePricingUpdate(BaseModel):
    gpu_hour_price: float
    cpu_hour_price: float
    ram_gb_hour_price: float
    storage_gb_month_price: float
    bandwidth_gb_price: float
    pricing_mode: str
