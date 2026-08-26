from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid

class ModelOut(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    runtime: str
    minimum_vram: int
    is_approved: bool

    class Config:
        from_attributes = True

class ModelCreate(BaseModel):
    name: str
    version: str
    runtime: str
    source: str
    minimum_vram: int
    minimum_ram: int
    minimum_cpu: int
    storage_requirement: int
    supported_gpu_families: Dict[str, Any]
    deployment_config: Dict[str, Any]
