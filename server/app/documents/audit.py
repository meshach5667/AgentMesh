import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, index


class AuditLog(Doc):
    user_id: uuid.UUID | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    details: Any = None
    ip_address: str | None = None
    created_at: datetime | None = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "audit_logs"
        indexes = [index("created_at"), index("user_id")]


class Event(Doc):
    type: str | None = None
    source: str | None = None
    data: Any = None
    created_at: datetime | None = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "events"
