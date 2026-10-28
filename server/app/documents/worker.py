import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, index, unique


class NodeEnrollmentToken(Doc):
    """Short-lived, single-use token a provider hands to a worker so it can enroll a node."""

    provider_id: uuid.UUID
    token_hash: str
    name: str | None = None
    region: str | None = None
    expires_at: datetime
    used_at: datetime | None = None
    node_id: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "node_enrollment_tokens"
        indexes = [unique("token_hash", name="uq_node_enrollment_tokens_token_hash"), index("provider_id")]


class CommandType(str, enum.Enum):  # noqa: UP042
    DEPLOY = "DEPLOY"
    STOP = "STOP"
    RESTART = "RESTART"  # stop the local runtime and deploy again from the cached model


class CommandStatus(str, enum.Enum):  # noqa: UP042
    PENDING = "PENDING"
    LEASED = "LEASED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NodeCommand(Doc):
    """Persisted command queue. Workers lease commands by polling outbound; the command id doubles as
    the idempotency key, so a redelivered command is never executed twice by a well-behaved worker."""

    node_id: uuid.UUID
    deployment_id: uuid.UUID | None = None
    type: str
    payload: Any
    status: str = CommandStatus.PENDING.value
    attempts: int = 0
    max_attempts: int = 3
    lease_expires_at: datetime | None = None
    # Not delivered before this time (e.g. the STOP of an old copy after a planned move lets in-flight requests end).
    not_before: datetime | None = None
    error: str | None = None
    # Signed authorization of the current lease (app.core.signing): its nonce must accompany the ack.
    auth_nonce: str | None = None
    auth_expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime | None = Field(default_factory=utcnow)
    completed_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "node_commands"
        indexes = [index("node_id", "status", "created_at"), index("deployment_id"), index("status")]
