import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, index, unique


class ApiKey(Doc):
    """Customer API key for the inference gateway. Only a SHA-256 hash of the secret is stored."""

    user_id: uuid.UUID
    name: str
    prefix: str
    key_hash: str
    scopes: Any
    # Optional restriction to a single deployment. None means all of the user's deployments.
    deployment_id: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=utcnow)
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "api_keys"
        indexes = [unique("key_hash", name="uq_api_keys_key_hash"), index("user_id")]
