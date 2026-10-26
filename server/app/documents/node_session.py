"""Short-lived node sessions obtained by proof of possession.

A worker proves it holds both its enrollment credential and the private key it registered at enrollment by signing a
fresh, single-use challenge. It then authenticates with a session token valid for ``NODE_SESSION_TTL_MINUTES`` and
renews it the same way. A stolen credential without the key, or the key without the credential, gets nothing.
"""

import uuid
from datetime import datetime

from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.core.timeutil import utcnow
from app.documents.base import Doc, index, unique


class NodeChallenge(Doc):
    node_id: uuid.UUID
    challenge_hash: str
    expires_at: datetime
    used_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "node_challenges"
        indexes = [
            unique("challenge_hash", name="uq_node_challenges_hash"),
            IndexModel([("expires_at", ASCENDING)], name="ttl_node_challenges", expireAfterSeconds=0),
        ]


class NodeSession(Doc):
    node_id: uuid.UUID
    token_hash: str
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    revoked_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "node_sessions"
        indexes = [
            unique("token_hash", name="uq_node_sessions_hash"),
            index("node_id"),
            IndexModel([("expires_at", ASCENDING)], name="ttl_node_sessions", expireAfterSeconds=0),
        ]
