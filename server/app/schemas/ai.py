import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.ai.policy import AutonomyLimits


class AiDeploymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: str = Field(min_length=5, max_length=2000, description="What to deploy, in your own words")
    limits: AutonomyLimits
    idempotency_key: str | None = Field(None, max_length=128)


class AiRunOut(BaseModel):
    id: uuid.UUID
    status: str
    request: str
    limits: dict[str, Any]
    plan: dict[str, Any] | None
    model_name: str | None
    deployment_id: uuid.UUID | None
    deployment_ids: list[str]
    deployment_status: str | None
    runtime: str | None
    endpoint: str | None = Field(description="Published only after a verified test completion")
    openai_base_url: str | None
    explanation: str | None = Field(description="Written by the AI model; informational only")
    error_code: str | None
    error_message: str | None
    currency: str | None
    estimated_hourly: Decimal | None
    estimated_total: Decimal | None
    actual_cost: Decimal
    recovery_attempts: int
    agent_steps: int
    tool_calls: int
    waiting_for_ai: bool
    cancel_requested: bool
    stop_reason: str | None
    deadline_at: datetime | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class AiRunEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    from_status: str | None
    to_status: str | None
    message: str | None
    data: dict[str, Any] | None
    created_at: datetime


class AiHealthOut(BaseModel):
    """Whether the AI service can answer, and which model answers."""

    status: str
    available: bool
    model: str
    queue_depth: int
    message: str
