from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional
import uuid

class MarketplaceNodeResponse(BaseModel):
    node_id: uuid.UUID
    name: Optional[str] = None
    region: Optional[str] = None
    gpu_model: Optional[str] = None
    gpu_count: int = 0
    gpu_vram_gb: Optional[int] = None
    cpu_model: Optional[str] = None
    cpu_cores: Optional[int] = None
    ram_gb: Optional[int] = None
    gpu_hour_price: Optional[Decimal] = None
    reputation_score: Decimal = Decimal("100.00")
    status: str
    model_config = {"from_attributes": True}

class MarketplaceSearchParams(BaseModel):
    min_vram_gb: Optional[int] = None
    min_ram_gb: Optional[int] = None
    min_cpu_cores: Optional[int] = None
    gpu_model: Optional[str] = None
    max_gpu_hour_price: Optional[Decimal] = None
    region: Optional[str] = None
    status: Optional[str] = "AVAILABLE"

class PricingRecommendation(BaseModel):
    gpu_model: str
    recommended_gpu_hour_price: Decimal
    market_low: Decimal
    market_high: Decimal
    market_median: Decimal
