"""Server-side login sessions and their rotating refresh tokens.

A session is created at sign-in. Access tokens (JWTs, ``ACCESS_TOKEN_EXPIRE_MINUTES``) name their session and are
honoured only while it exists and is not revoked, so logout, disabling an account and refresh-token reuse take
effect immediately. Each refresh token works once: using it issues the next one. Presenting a token that was
already used means it was copied, so the whole session is revoked (reuse detection).
"""

import uuid
from datetime import datetime

from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.core.timeutil import utcnow
from app.documents.base import Doc, index, unique


class AuthSession(Doc):
    user_id: uuid.UUID
    created_at: datetime = Field(default_factory=utcnow)
    last_used_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime  # absolute lifetime; refreshing does not extend it
    revoked_at: datetime | None = None
    revoke_reason: str | None = None
    # Whether this sign-in completed a second factor (required for staff when STAFF_MFA_REQUIRED).
    mfa_verified: bool = False
    # Kept for security investigations only, and deleted with the session.
    ip_address: str | None = None
    user_agent: str | None = None

    class Settings(Doc.Settings):
        name = "auth_sessions"
        indexes = [
            index("user_id"),
            IndexModel([("expires_at", ASCENDING)], name="ttl_auth_sessions", expireAfterSeconds=0),
        ]


class RefreshToken(Doc):
    session_id: uuid.UUID
    token_hash: str
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    used_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "refresh_tokens"
        indexes = [
            unique("token_hash", name="uq_refresh_tokens_hash"),
            index("session_id"),
            IndexModel([("expires_at", ASCENDING)], name="ttl_refresh_tokens", expireAfterSeconds=0),
        ]
