"""AI deployment agent: runs (persistent workflow state), their event history, the inference request queue
that internal inference machines pull from, and those machines' last reported health.

Workflow state lives here, not in the model conversation, so a run resumes after a control-plane restart
and a deployment keeps running while the inference machine is offline.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, Money, index, unique


class AiRun(Doc):
    """One natural-language deployment request and everything the agent did for it. Valid status changes are
    defined in app.services.ai.workflow. Deleting a run deletes its events and inference requests."""

    customer_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    idempotency_key: str | None = None
    request_text: str  # the customer's own words (untrusted)
    limits: Any  # validated AutonomyLimits
    plan: Any = None  # validated DeploymentPlan
    # Current deployment, and every deployment this run created (recovery creates new ones).
    deployment_id: uuid.UUID | None = None
    deployment_ids: Any = None
    currency: str | None = None
    estimated_hourly: Money | None = None
    estimated_total: Money | None = None
    # Agent bookkeeping. ``conversation`` is the bounded transcript of the current planning or diagnosis
    # conversation; ``pending_request_id`` is the inference request the run is waiting for.
    phase: str | None = None  # planning | recovery
    conversation: Any = None
    pending_request_id: uuid.UUID | None = None
    agent_steps: int = 0
    tool_calls: int = 0
    recovery_attempts: int = 0
    probe_failures: int = 0
    # Latest model-written explanation for the customer. Always shown as AI-generated, never as fact.
    explanation: str | None = None
    endpoint: str | None = None  # published only after a verified inference
    error_code: str | None = None
    error_message: str | None = None
    cancel_requested: bool = False
    stop_reason: str | None = None
    deadline_at: datetime | None = None  # max duration, from first submission
    # Processing lease so only one API replica advances a run at a time.
    lease_owner: str | None = None
    lease_until: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "ai_runs"
        indexes = [
            unique(
                "customer_id", "idempotency_key", name="uq_ai_runs_customer_idempotency", nullable=("idempotency_key",)
            ),
            index("customer_id", "created_at"),
            index("status"),
            index("created_at"),
        ]


class AiRunEvent(Doc):
    """Append-only history of a run: state changes, tool calls, AI decisions, and waits."""

    run_id: uuid.UUID
    kind: str  # state | tool | ai | info | error
    from_status: str | None = None
    to_status: str | None = None
    message: str | None = None
    data: Any = None
    created_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "ai_run_events"
        indexes = [index("run_id", "created_at")]


class AiInferenceRequest(Doc):
    """One model call, waiting for an inference machine to lease it. Prompts are stored only until answered."""

    run_id: uuid.UUID | None = None
    purpose: str  # planning | recovery
    model: str
    payload: Any = None  # messages, output schema, options
    # PENDING | LEASED | COMPLETED | FAILED | EXPIRED | CANCELLED
    status: str = "PENDING"
    attempts: int = 0
    max_attempts: int = 2
    node_id: str | None = None  # inference machine holding/answering it
    lease_expires_at: datetime | None = None
    result: Any = None  # {"content": ..., token counts}
    error_code: str | None = None
    error: str | None = None
    latency_ms: int | None = None
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    completed_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "ai_inference_requests"
        indexes = [index("run_id"), index("status", "created_at"), index("created_at")]
