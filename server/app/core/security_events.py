"""Structured security events, written as log records with an explicit allowlist of fields.

Only identifiers, outcomes and reasons are recorded: never prompts, outputs, tokens, keys or request bodies. Events
that need a durable trail (administrative actions, revocations) are also written to the audit log by their callers.
"""

import logging
from typing import Any

logger = logging.getLogger("agentmesh.security")

ALLOWED_FIELDS = frozenset(
    {"node_id", "user_id", "session_id", "deployment_id", "command_id", "reason", "status", "count", "kid"}
)


def emit(event: str, **fields: Any) -> None:
    safe = {k: str(v)[:200] for k, v in fields.items() if k in ALLOWED_FIELDS and v is not None}
    dropped = sorted(set(fields) - ALLOWED_FIELDS)
    if dropped:
        safe["dropped_fields"] = ",".join(dropped)
    logger.warning("security_event=%s %s", event, " ".join(f"{k}={v}" for k, v in sorted(safe.items())))
