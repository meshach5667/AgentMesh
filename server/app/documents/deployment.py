import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, index, unique


class DeploymentStatus(str, enum.Enum):  # noqa: UP042
    """Lifecycle states. Valid transitions are defined in app.services.deployment_lifecycle."""

    REQUESTED = "REQUESTED"
    SCHEDULED = "SCHEDULED"
    PROVISIONING = "PROVISIONING"
    STARTING = "STARTING"
    READY = "READY"
    UNHEALTHY = "UNHEALTHY"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Deployment(Doc):
    customer_id: uuid.UUID | None = None
    model_id: uuid.UUID | None = None
    node_id: uuid.UUID | None = None
    status: str | None = DeploymentStatus.REQUESTED.value
    endpoint: str | None = None
    config: Any = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    runtime: str | None = None
    model_tag: str | None = None
    model_digest: str | None = None  # reported by the worker after pulling
    idempotency_key: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    ready_at: datetime | None = None
    last_health_at: datetime | None = None
    was_ready: bool = False
    cleanup_status: str | None = None  # pending | done | pending_node
    deleted_at: datetime | None = None
    updated_at: datetime | None = Field(default_factory=utcnow)
    # Placement history: how many nodes this deployment has been scheduled onto, and which nodes failed it.
    schedule_attempts: int = 0
    excluded_node_ids: Any = None
    restart_count: int = 0
    artifact_id: uuid.UUID | None = None
    # Billing watermark: READY time and tokens before this instant have been rated into charges.
    metered_until: datetime | None = None

    class Settings(Doc.Settings):
        name = "deployments"
        indexes = [
            unique(
                "customer_id",
                "idempotency_key",
                name="uq_deployments_customer_idempotency",
                nullable=("idempotency_key",),
            ),
            index("customer_id", "created_at"),
            index("status"),
            index("node_id"),
        ]


class DeploymentEvent(Doc):
    """Append-only lifecycle history, shown to customers for progress and troubleshooting."""

    deployment_id: uuid.UUID | None = None
    from_status: str | None = None
    to_status: str | None = None
    actor: str  # customer | worker | system | operator
    # Node the deployment was placed on when the event happened (billing attributes READY time by it).
    node_id: uuid.UUID | None = None
    message: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "deployment_events"
        indexes = [index("deployment_id", "created_at")]
