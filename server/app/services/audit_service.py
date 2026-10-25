"""Audit trail for security-relevant actions by customers, providers, operators, and workers.

Rows are added to the caller's transaction (no commit here), so an action and its audit record are saved
together or not at all. Secrets and prompt contents never go into ``details``.
"""

import uuid
from typing import Any

from app.core.database import Session
from app.core.logging import client_ip_var, redact, request_id_var
from app.documents.audit import AuditLog


def record(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: Any,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    safe = {k: redact(v) if isinstance(v, str) else v for k, v in (details or {}).items()}
    if request_id_var.get():
        safe["request_id"] = request_id_var.get()
    entry = AuditLog(
        user_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        details=safe,
        ip_address=client_ip_var.get(),
    )
    db.add(entry)
    return entry


async def search(
    db: Session,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    actor_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[AuditLog]:
    filter: dict[str, Any] = {}
    if action:
        filter["action"] = action
    if resource_type:
        filter["resource_type"] = resource_type
    if resource_id:
        filter["resource_id"] = resource_id
    if actor_id:
        filter["user_id"] = actor_id
    return await db.find(AuditLog, filter, sort=[("created_at", -1)], limit=min(max(limit, 1), 500))
