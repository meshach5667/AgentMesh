import uuid
from datetime import timedelta

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import Session
from app.core.logging import client_ip_var
from app.core.security import (
    REFRESH_TOKEN_PREFIX,
    burn_password_check,
    create_access_token,
    generate_secret,
    get_password_hash,
    hash_secret,
    password_needs_rehash,
    verify_password,
)
from app.core.timeutil import utcnow
from app.documents.session import AuthSession, RefreshToken
from app.documents.user import Customer, Provider, User, UserRole
from app.schemas.auth import UserCreate, UserLogin
from app.services import audit_service

INVALID_REFRESH = HTTPException(status_code=401, detail="Session expired. Sign in again.")


async def _new_refresh_token(db: Session, session: AuthSession) -> str:
    token = generate_secret(REFRESH_TOKEN_PREFIX)
    db.add(RefreshToken(session_id=session.id, token_hash=hash_secret(token), expires_at=session.expires_at))
    return token


async def start_session(db: Session, user: User, *, user_agent: str | None = None, mfa_verified: bool = False) -> dict:
    """Create a session for ``user`` and return its first access and refresh tokens. The caller commits."""
    now = utcnow()
    session = AuthSession(
        user_id=user.id,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        mfa_verified=mfa_verified,
        ip_address=client_ip_var.get(),
        user_agent=(user_agent or "")[:200] or None,
    )
    db.add(session)
    refresh = await _new_refresh_token(db, session)
    return {
        "access_token": create_access_token(user.id, session.id),
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user,
    }


async def register_user(db: Session, user_data: UserCreate, user_agent: str | None = None):
    if await db.find_one(User, {"email": user_data.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=user_data.email, hashed_password=get_password_hash(user_data.password), role=user_data.role.value)
    db.add(user)
    await db.flush()  # assign user.id without committing, so user + profile are created atomically

    if user.role == UserRole.provider.value:
        db.add(Provider(user_id=user.id))
    elif user.role == UserRole.customer.value:
        db.add(Customer(user_id=user.id))
    audit_service.record(
        db,
        actor_id=user.id,
        action="user.registered",
        resource_type="user",
        resource_id=user.id,
        details={"role": user.role},
    )
    tokens = await start_session(db, user, user_agent=user_agent)
    await db.commit()
    return tokens


async def authenticate(db: Session, user_data: UserLogin) -> User:
    """Check email and password. Every failure looks the same and costs the same."""
    user = await db.find_one(User, {"email": user_data.email})
    if user is None:
        burn_password_check(user_data.password)
    if not user or not verify_password(user_data.password, user.hashed_password):
        audit_service.record(
            db,
            actor_id=user.id if user else None,
            action="auth.login_failed",
            resource_type="user",
            resource_id=user.id if user else None,
            details={"email": user_data.email},
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    if password_needs_rehash(user.hashed_password):
        user.hashed_password = get_password_hash(user_data.password)
    return user


async def login(db: Session, user_data: UserLogin, user_agent: str | None = None):
    user = await authenticate(db, user_data)
    audit_service.record(db, actor_id=user.id, action="auth.login", resource_type="user", resource_id=user.id)
    tokens = await start_session(db, user, user_agent=user_agent)
    await db.commit()
    return tokens


async def revoke_session(db: Session, session: AuthSession, reason: str, actor_id: uuid.UUID | None) -> None:
    """End a session at once: its access tokens stop working on the next request. The caller commits."""
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        session.revoke_reason = reason
        audit_service.record(
            db,
            actor_id=actor_id,
            action="auth.session_revoked",
            resource_type="session",
            resource_id=session.id,
            details={"reason": reason, "user_id": str(session.user_id)},
        )


async def refresh(db: Session, token: str):
    """Exchange a refresh token for new tokens. Each refresh token works once; a reused one revokes its session."""
    if not token.startswith(REFRESH_TOKEN_PREFIX):
        raise INVALID_REFRESH
    now = utcnow()
    row = await db.find_one(RefreshToken, {"token_hash": hash_secret(token)})
    session = await db.get(AuthSession, row.session_id) if row else None
    if row is None or session is None or session.revoked_at is not None or session.expires_at <= now:
        raise INVALID_REFRESH
    # Claim the token atomically: of two concurrent uses, exactly one wins and the other counts as reuse.
    claimed = row.used_at is None and await db.update_one(
        RefreshToken, {"_id": row.id, "used_at": None}, {"$set": {"used_at": now}}
    )
    if not claimed:
        await db.rollback()
        session = await db.get(AuthSession, row.session_id)
        if session is not None:
            await revoke_session(db, session, "refresh_token_reuse", actor_id=None)
            await db.commit()
        raise INVALID_REFRESH
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        await revoke_session(db, session, "account_disabled", actor_id=None)
        await db.commit()
        raise INVALID_REFRESH
    session.last_used_at = now
    new_refresh = await _new_refresh_token(db, session)
    await db.commit()
    return {
        "access_token": create_access_token(user.id, session.id),
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user,
    }


async def revoke_all_sessions(db: Session, user_id: uuid.UUID, reason: str, actor_id: uuid.UUID | None) -> int:
    sessions = await db.find(AuthSession, {"user_id": user_id, "revoked_at": None})
    for session in sessions:
        await revoke_session(db, session, reason, actor_id)
    return len(sessions)
