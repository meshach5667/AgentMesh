import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelOut(BaseModel):
    id: uuid.UUID
    name: str
    version: str | None = None
    runtime: str | None = None
    minimum_vram: int | None = None
    minimum_ram: int | None = None
    is_approved: bool
    model_tag: str | None = None
    publisher: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    format: str | None = None
    license: str | None = None
    context_length: int | None = None
    download_size_mb: int | None = None
    min_ram_mb: int | None = None
    min_disk_mb: int | None = None
    min_vram_mb: int | None = None
    min_cpu_cores: int | None = None
    gpu_required: bool = False
    requirements_estimated: bool = True

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class ModelCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(max_length=255)
    version: str = Field(max_length=50)
    runtime: str = Field(max_length=50)
    source: str = Field(max_length=500)
    minimum_vram: int = 0
    minimum_ram: int = 0
    minimum_cpu: int = 0
    storage_requirement: int = 0
    supported_gpu_families: dict[str, Any] = Field(default_factory=dict)
    deployment_config: dict[str, Any] = Field(default_factory=dict)

    model_tag: str | None = Field(None, max_length=255)
    publisher: str | None = Field(None, max_length=255)
    family: str | None = Field(None, max_length=100)
    parameter_size: str | None = Field(None, max_length=50)
    quantization: str | None = Field(None, max_length=50)
    format: str | None = Field(None, max_length=50)
    license: str | None = Field(None, max_length=255)
    context_length: int | None = Field(None, ge=1)
    download_size_mb: int | None = Field(None, ge=0)
    min_ram_mb: int | None = Field(None, ge=1)
    min_disk_mb: int | None = Field(None, ge=1)
    min_vram_mb: int | None = Field(None, ge=0)
    min_cpu_cores: int | None = Field(None, ge=1)
    gpu_required: bool = False
    requirements_estimated: bool = True

    @field_validator("model_tag")
    @classmethod
    def _valid_tag(cls, v: str | None) -> str | None:
        from app.services.catalog_service import OLLAMA_TAG_RE

        if v is not None and not OLLAMA_TAG_RE.fullmatch(v):
            raise ValueError("model_tag must be a plain runtime model reference such as 'qwen2.5:0.5b'")
        return v
