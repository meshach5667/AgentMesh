"""Time-based one-time passwords (RFC 6238) as a second factor, using ``cryptography``'s TOTP.

Staff accounts must complete a second factor before staff features work when ``STAFF_MFA_REQUIRED`` (the default).
The seed is stored encrypted (``app.core.crypto``). A code is accepted for its 30-second step and one step either
side for clock drift, and each step is accepted once, so a code seen over a shoulder cannot be replayed.
"""

import base64
import hmac
import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives.twofactor.totp import TOTP
from fastapi import HTTPException

from app.core import crypto
from app.core.config import settings
from app.core.database import Session
from app.core.dependencies import is_staff
from app.core.keys import derive_key
from app.core.security import ALGORITHM, TOKEN_AUDIENCE, TOKEN_CLOCK_LEEWAY_SECONDS
from app.core.timeutil import utcnow
from app.documents.session import AuthSession
from app.documents.user import User
from app.services import audit_service

STEP_SECONDS = 30
CHALLENGE_MINUTES = 5
BAD_CODE = HTTPException(status_code=401, detail="Invalid or already used code")


def _context(user: User) -> str:
    return f"user:{user.id}:totp"


def _totp(seed: bytes) -> TOTP:
    return TOTP(seed, 6, SHA1(), STEP_SECONDS, enforce_key_length=True)


def _seed(user: User, field: str) -> bytes | None:
    value = getattr(user, field)
    return crypto.decrypt(value, _context(user)) if value else None


def mfa_required_for(user: User) -> bool:
    return settings.STAFF_MFA_REQUIRED and is_staff(user)


def _accept(user: User, seed: bytes, code: str, now: float | None = None) -> int | None:
    """The time step ``code`` belongs to, if it is valid and newer than the last accepted step."""
    if not (len(code) == 6 and code.isdigit()):
        return None
    now = time.time() if now is None else now
    totp = _totp(seed)
    current = int(now // STEP_SECONDS)
    for step in (current - 1, current, current + 1):
        if step <= (user.mfa_last_step or -1):
            continue
        if hmac.compare_digest(totp.generate(step * STEP_SECONDS), code.encode()):
            return step
    return None


async def begin_setup(db: Session, user: User) -> dict:
    if user.mfa_secret:
        raise HTTPException(status_code=409, detail="Two-factor authentication is already on")
    seed = os.urandom(20)
    user.mfa_pending_secret = crypto.encrypt(seed, _context(user))
    await db.commit()
    return {
        "secret": base64.b32encode(seed).decode().rstrip("="),
        "otpauth_uri": _totp(seed).get_provisioning_uri(user.email, settings.MFA_ISSUER),
    }


async def enable(db: Session, user: User, session: AuthSession, code: str) -> None:
    seed = _seed(user, "mfa_pending_secret")
    if seed is None:
        raise HTTPException(status_code=409, detail="Start setup first")
    step = _accept(user, seed, code)
    if step is None:
        raise BAD_CODE
    user.mfa_secret, user.mfa_pending_secret = user.mfa_pending_secret, None
    user.mfa_last_step, user.mfa_enabled_at = step, utcnow()
    session.mfa_verified = True
    audit_service.record(db, actor_id=user.id, action="auth.mfa_enabled", resource_type="user", resource_id=user.id)
    await db.commit()


async def disable(db: Session, user: User, code: str) -> None:
    if mfa_required_for(user):
        raise HTTPException(status_code=403, detail="Staff accounts must keep two-factor authentication on")
    seed = _seed(user, "mfa_secret")
    if seed is None:
        raise HTTPException(status_code=409, detail="Two-factor authentication is not on")
    if _accept(user, seed, code) is None:
        raise BAD_CODE
    user.mfa_secret = user.mfa_pending_secret = None
    user.mfa_last_step = user.mfa_enabled_at = None
    audit_service.record(db, actor_id=user.id, action="auth.mfa_disabled", resource_type="user", resource_id=user.id)
    await db.commit()


def challenge_token(user: User) -> str:
    """Proof that the password was right, good only for completing the second factor within a few minutes."""
    now = datetime.now(UTC)
    claims = {"sub": str(user.id), "typ": "mfa", "aud": TOKEN_AUDIENCE, "iat": now, "jti": uuid.uuid4().hex}
    return str(jwt.encode(claims | {"exp": now + timedelta(minutes=CHALLENGE_MINUTES)}, _key(), algorithm=ALGORITHM))


def _key() -> bytes:
    return derive_key("mfa-challenge")


async def complete_login(db: Session, token: str, code: str) -> User:
    """Check the challenge token and the code; returns the user, whose step is recorded. The caller starts the
    session and commits."""
    try:
        claims = jwt.decode(
            token,
            _key(),
            algorithms=[ALGORITHM],
            audience=TOKEN_AUDIENCE,
            leeway=TOKEN_CLOCK_LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "sub", "typ", "aud"]},
        )
        if claims["typ"] != "mfa":
            raise ValueError
        user = await db.get(User, uuid.UUID(claims["sub"]))
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="Sign-in expired. Start again.") from None
    seed = _seed(user, "mfa_secret") if user is not None and user.is_active else None
    step = _accept(user, seed, code) if user is not None and seed is not None else None
    if user is None or step is None:
        if user is not None:
            audit_service.record(
                db, actor_id=user.id, action="auth.mfa_failed", resource_type="user", resource_id=user.id
            )
            await db.commit()
        raise BAD_CODE
    # Record the step atomically so the same code cannot complete two sign-ins.
    claimed = await db.update_one(
        User,
        {"_id": user.id, "$or": [{"mfa_last_step": None}, {"mfa_last_step": {"$lt": step}}]},
        {"$set": {"mfa_last_step": step}},
    )
    if not claimed:
        raise BAD_CODE
    user.mfa_last_step = step
    return user
