import uuid
from typing import Any

from pydantic import BaseModel


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
    supported_gpu_families: dict[str, Any]
    deployment_config: dict[str, Any]
