import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, index, unique


class Model(Doc):
    """Catalog entry. Appearing here does not make a model deployable: it must be approved, its runtime
    must be supported, and an eligible node with enough free capacity must exist at deploy time."""

    name: str
    version: str | None = None
    runtime: str | None = None
    source: str | None = None
    minimum_vram: int | None = None
    minimum_ram: int | None = None
    minimum_cpu: int | None = None
    storage_requirement: int | None = None
    supported_gpu_families: Any = None
    deployment_config: Any = None
    is_approved: bool | None = False
    created_at: datetime | None = Field(default_factory=utcnow)

    # Runtime-specific identifier, e.g. an Ollama tag such as "qwen2.5:0.5b".
    model_tag: str | None = None
    publisher: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    format: str | None = None
    license: str | None = None
    context_length: int | None = None
    download_size_mb: int | None = None

    # Resource requirements used by the scheduler. These are estimates unless stated otherwise.
    min_ram_mb: int | None = None
    min_disk_mb: int | None = None
    min_vram_mb: int | None = None
    min_cpu_cores: int | None = None
    gpu_required: bool = False
    requirements_estimated: bool = True

    # Community models: imported by a customer from Hugging Face, visible and deployable only by that customer
    # while unapproved. Operator approval makes one a reviewed catalog entry.
    owner_customer_id: uuid.UUID | None = None
    source_url: str | None = None
    withdrawn_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "models"
        indexes = [index("model_tag"), index("owner_customer_id")]


class ModelArtifact(Doc):
    """How one model is served by one runtime: where the weights come from (pinned), what they need, and
    whether serving them has actually worked. A model may have several (e.g. Ollama tag, GGUF for llama.cpp,
    safetensors for vLLM); compatibility is explicit, never assumed. Deleted together with its model."""

    model_id: uuid.UUID
    runtime: str  # ollama | llamacpp | vllm
    source_type: str  # ollama | huggingface
    # Ollama tag, or Hugging Face repository id. Also the name the model is served under.
    reference: str
    revision: str | None = None  # pinned Hugging Face commit
    file: str | None = None  # GGUF file for llama.cpp
    sha256: str | None = None
    size_bytes: int | None = None
    format: str | None = None  # ollama | gguf | safetensors
    quantization: str | None = None
    min_ram_mb: int
    min_disk_mb: int
    min_vram_mb: int = 0
    min_cpu_cores: int = 1
    gpu_required: bool = False
    requirements_estimated: bool = True
    is_enabled: bool = True
    # Set when a deployment of this artifact passes its readiness test: evidence it really works.
    last_ready_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "model_artifacts"
        indexes = [unique("model_id", "runtime", name="uq_model_artifacts_model_runtime")]
