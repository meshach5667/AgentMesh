import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.documents.deployment import DeploymentStatus

FailoverPolicy = Literal["any_provider", "same_provider", "manual"]
LIMIT_HOURLY = Field(
    None,
    ge=0,
    le=Decimal("1000000"),
    max_digits=18,
    decimal_places=8,
    description="Most to pay per hour for the reserved CPU, RAM and VRAM. Omit for no limit on the first "
    "placement; a move after a failure then costs at most what the failed placement did",
)
LIMIT_TOKENS = Field(
    None,
    ge=0,
    le=Decimal("1000000"),
    max_digits=18,
    decimal_places=8,
    description="Most to pay per million input or output tokens (same defaults as max_hourly_price)",
)


class DeploymentCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_id: uuid.UUID
    runtime: Literal["ollama", "llamacpp", "vllm"] | None = Field(
        None, description="Serve with this runtime. Omit to let AgentMesh pick any compatible runtime"
    )
    config: dict[str, Any] = Field(default_factory=dict, description="num_ctx, region, require_gpu")
    idempotency_key: str | None = Field(
        None, max_length=128, description="Retries with the same key return the same deployment"
    )
    currency: str | None = Field(
        None, pattern=r"^[A-Z]{3}$", description="Currency of the price limits; default DEFAULT_CURRENCY"
    )
    max_hourly_price: Decimal | None = LIMIT_HOURLY
    max_token_price: Decimal | None = LIMIT_TOKENS
    provider_id: uuid.UUID | None = Field(None, description="Run only on this provider's machines")
    failover_policy: FailoverPolicy = Field(
        "any_provider",
        description="When the node fails: move to any eligible provider's machine, only to the same provider's, "
        "or never automatically (manual)",
    )


class DeploymentUpdate(BaseModel):
    """Applies to the next placement (a move after a failure, or a retry)."""

    model_config = ConfigDict(extra="forbid")
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    max_hourly_price: Decimal | None = LIMIT_HOURLY
    max_token_price: Decimal | None = LIMIT_TOKENS
    failover_policy: FailoverPolicy | None = None


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: uuid.UUID
    customer_id: uuid.UUID
    model_id: uuid.UUID
    node_id: uuid.UUID | None
    status: DeploymentStatus
    endpoint: str | None
    runtime: str | None = None
    model_tag: str | None = None
    model_digest: str | None = None
    config: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    ready_at: datetime | None = None
    ended_at: datetime | None = None
    cleanup_status: str | None = None
    schedule_attempts: int = 0
    restart_count: int = 0
    artifact_id: uuid.UUID | None = None
    currency: str | None = None
    max_hourly_price: Decimal | None = None
    max_token_price: Decimal | None = None
    provider_id: uuid.UUID | None = None
    failover_policy: str = "any_provider"
    attempt_id: uuid.UUID | None = None
    # While PENDING: next automatic retry, since when it has waited, and retries so far.
    next_placement_at: datetime | None = None
    pending_since: datetime | None = None
    placement_retries: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def openai_base_url(self) -> str | None:
        """OpenAI-compatible base URL; works for every runtime (append /chat/completions etc.)."""
        if not self.endpoint:
            return None
        return self.endpoint.rsplit("/", 1)[0] + "/v1"


class DeploymentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    from_status: str | None
    to_status: str | None
    actor: str
    message: str | None
    kind: str | None = None
    attempt: int | None = None
    created_at: datetime
