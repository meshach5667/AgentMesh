import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, Money, index, unique


class DeploymentStatus(str, enum.Enum):  # noqa: UP042
    """Lifecycle states. Valid transitions are defined in app.services.deployment_lifecycle."""

    REQUESTED = "REQUESTED"
    PENDING = "PENDING"  # its node failed and no eligible replacement exists yet: retried with backoff
    NEEDS_ATTENTION = "NEEDS_ATTENTION"  # automatic recovery stopped; waits for the customer (see failover policy)
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
    # Price limits for every placement, in ``currency``: per hour of the reservation, and per million tokens (input
    # or output). Without a limit, a move after a failure may not cost more than the placement it replaces.
    currency: str | None = None
    max_hourly_price: Money | None = None
    max_token_price: Money | None = None
    # Customer constraints on placement: only this provider's machines (None: any provider), and what happens when
    # the node fails: "any_provider" moves it anywhere eligible, "same_provider" only to the same provider's
    # machines, "manual" never moves it automatically (NEEDS_ATTENTION instead).
    provider_id: uuid.UUID | None = None
    failover_policy: str = "any_provider"
    # Current execution attempt (see DeploymentAttempt). Worker reports naming another attempt are stale.
    attempt_id: uuid.UUID | None = None
    # While PENDING: when placement is retried next, when waiting began, and how many retries were made.
    next_placement_at: datetime | None = None
    pending_since: datetime | None = None
    placement_retries: int = 0
    # Cost-estimate watermark: READY time and tokens before this instant have been estimated.
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
            index("status", "next_placement_at"),
        ]


class DeploymentAttempt(Doc):
    """One placement of a deployment on a node, from assignment until it ends. A deployment that is moved after a
    failure gets a new attempt; at most one attempt per deployment is active (unique partial index), so two
    schedulers can never both assign it."""

    deployment_id: uuid.UUID
    number: int
    node_id: uuid.UUID
    provider_id: uuid.UUID | None = None
    active: bool = True
    # assigned -> running (READY at least once) -> ended
    state: str = "assigned"
    # How it ended: node_failed, workload_failed, stopped, superseded
    outcome: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    rates: dict[str, str] | None = None  # unit prices in force when it was placed: the most it is charged there
    assigned_at: datetime = Field(default_factory=utcnow)
    ready_at: datetime | None = None
    ended_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "deployment_attempts"
        indexes = [
            unique("deployment_id", "number", name="uq_deployment_attempts_number"),
            unique("deployment_id", name="uq_deployment_attempts_active", where={"active": True}),
            index("node_id", "active"),
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
    # What happened, for recovery history: assigned, attempt_failed, retry_scheduled, rerouted, no_replacement,
    # retry_limit, approval_required, recovered. None for plain progress notes.
    kind: str | None = None
    attempt: int | None = None
    created_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "deployment_events"
        indexes = [index("deployment_id", "created_at")]
