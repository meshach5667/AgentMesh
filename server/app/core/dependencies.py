from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.database import Session, get_db
from app.core.security import decode_access_token
from app.core.timeutil import utcnow
from app.documents.session import AuthSession
from app.documents.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

STAFF_ROLES = frozenset({UserRole.operator.value, UserRole.admin.value})


class InvalidCredentials(Exception):  # noqa: N818
    pass


async def resolve_access_token(db: Session, token: str) -> tuple[User, AuthSession]:
    """The active user and live session an access token belongs to. Anything doubtful is rejected: a bad
    signature, a missing claim, an expired, revoked or unknown session, or a disabled account."""
    try:
        user_id, session_id = decode_access_token(token)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise InvalidCredentials from None
    session = await db.get(AuthSession, session_id)
    if (
        session is None
        or session.user_id != user_id
        or session.revoked_at is not None
        or session.expires_at <= utcnow()
    ):
        raise InvalidCredentials
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise InvalidCredentials
    return user, session


async def get_current_user(
    request: Request, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """Resolve the bearer token to an active user with a live session. The session is kept on ``request.state``."""
    try:
        user, session = await resolve_access_token(db, token)
    except InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    request.state.auth_session = session
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def require_roles(*roles: str) -> Callable:
    """Dependency factory enforcing role-based access on the backend."""
    allowed = frozenset(r.value if isinstance(r, UserRole) else r for r in roles)

    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return _checker


def is_staff(user: User) -> bool:
    return user.role in STAFF_ROLES
