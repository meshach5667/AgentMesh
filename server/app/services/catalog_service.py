"""Model catalog validation: decides whether a catalog entry can be deployed and with what resources."""

import math
import re
from dataclasses import dataclass

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import parse_uuid
from app.models.model import Model

# Runtimes the control plane can currently schedule. Others may exist in the catalog but are rejected
# with an explicit message rather than silently attempted.
SUPPORTED_RUNTIMES = frozenset({"ollama"})

# Ollama model references: optional namespace, name, optional tag. No URLs, paths, or shell metacharacters.
OLLAMA_TAG_RE = re.compile(
    r"^[a-z0-9][a-z0-9._-]{0,63}(/[a-z0-9][a-z0-9._-]{0,63})?(:[a-zA-Z0-9][a-zA-Z0-9._-]{0,63})?$"
)

MAX_NUM_CTX = 8192
DEFAULT_NUM_CTX = 2048


class DeploymentConfig(BaseModel):
    """Allowlisted deployment options. Unknown keys are rejected rather than passed to the runtime."""

    model_config = ConfigDict(extra="forbid")

    num_ctx: int = Field(DEFAULT_NUM_CTX, ge=512, le=MAX_NUM_CTX, description="Context window in tokens")
    region: str | None = Field(None, max_length=100)
    require_gpu: bool = False


@dataclass(frozen=True)
class ResourceRequest:
    runtime: str
    cpu_cores: int
    ram_mb: int
    disk_mb: int
    vram_mb: int
    gpu_required: bool
    region: str | None = None


def validate_model_tag(tag: str | None) -> str:
    if not tag or not OLLAMA_TAG_RE.fullmatch(tag):
        raise HTTPException(status_code=422, detail="Model has no valid runtime identifier")
    return tag


async def get_deployable_model(db: AsyncSession, model_id) -> Model:
    model = await db.get(Model, parse_uuid(model_id, "Model"))
    if not model or not model.is_approved:
        raise HTTPException(status_code=404, detail="Approved model not found")
    if model.runtime not in SUPPORTED_RUNTIMES:
        raise HTTPException(
            status_code=422,
            detail=f"Runtime '{model.runtime}' is not supported yet. "
            f"Supported: {', '.join(sorted(SUPPORTED_RUNTIMES))}",
        )
    validate_model_tag(model.model_tag)
    if not model.min_ram_mb or not model.min_disk_mb:
        raise HTTPException(
            status_code=422, detail="Model has no resource requirements recorded and cannot be scheduled"
        )
    return model


def estimate_requirements(model: Model, config: DeploymentConfig) -> ResourceRequest:
    """Scheduler reservation for a model. Catalog figures assume the default context; larger contexts need
    more KV-cache memory, approximated at 128 MB per extra 2048 tokens. These are estimates."""
    extra_ctx_mb = max(0, math.ceil((config.num_ctx - DEFAULT_NUM_CTX) / 2048)) * 128
    gpu = bool(model.gpu_required or config.require_gpu)
    return ResourceRequest(
        runtime=model.runtime,
        cpu_cores=max(1, model.min_cpu_cores or 1),
        ram_mb=model.min_ram_mb + extra_ctx_mb,
        disk_mb=model.min_disk_mb,
        vram_mb=(model.min_vram_mb or 0) if gpu else 0,
        gpu_required=gpu,
        region=config.region,
    )
