import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from passlib.context import CryptContext

from app.core.config import settings

# Passwords: Argon2id with argon2-cffi's defaults (RFC 9106 low-memory profile). Hashes made before Argon2 (PBKDF2
# or bcrypt through passlib) still verify and are replaced with Argon2id at the next successful login.
password_hasher = PasswordHasher()
legacy_pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
pwd_context = legacy_pwd_context  # legacy node API keys (see verify_node_api_key)
ALGORITHM = "HS256"
_dummy_hash: str | None = None


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith("$argon2"):
        try:
            return password_hasher.verify(hashed_password, plain_password)
        except (VerificationError, InvalidHashError):
            return False
    try:
        return bool(legacy_pwd_context.verify(plain_password, hashed_password))
    except (ValueError, TypeError):
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    return not hashed_password.startswith("$argon2") or password_hasher.check_needs_rehash(hashed_password)


def get_password_hash(password: str) -> str:
    return password_hasher.hash(password)


def burn_password_check(plain_password: str) -> None:
    """Spend the same time as a real check when there is no account, so response timing does not reveal which
    emails are registered."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = password_hasher.hash("agentmesh-dummy-password")
    verify_password(plain_password, _dummy_hash)


SHA256_PREFIX = "sha256$"


def generate_secret(prefix: str, nbytes: int = 32) -> str:
    """High-entropy bearer secret, e.g. ``am_sk_...``. Never stored in plaintext."""
    return f"{prefix}{secrets.token_urlsafe(nbytes)}"


def hash_secret(secret: str) -> str:
    """Hash a high-entropy machine secret. SHA-256 is appropriate here (unlike for passwords) because the
    secret has ~256 bits of entropy and must be verified on every request."""
    return SHA256_PREFIX + hashlib.sha256(secret.encode()).hexdigest()


def verify_secret(secret: str, stored_hash: str | None) -> bool:
    if not stored_hash or not stored_hash.startswith(SHA256_PREFIX):
        return False
    return hmac.compare_digest(hash_secret(secret), stored_hash)


def verify_node_api_key(plain_key: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    if stored_hash.startswith(SHA256_PREFIX):
        return verify_secret(plain_key, stored_hash)
    # Legacy keys issued by POST /nodes/register before Phase 2 were hashed with the password context.
    try:
        return bool(pwd_context.verify(plain_key, stored_hash))
    except (ValueError, TypeError):
        return False


TOKEN_AUDIENCE = "agentmesh-api"
TOKEN_CLOCK_LEEWAY_SECONDS = 30  # replicas' clocks may differ slightly
REFRESH_TOKEN_PREFIX = "am_rt_"


def _access_key() -> bytes:
    from app.core.keys import derive_key

    return derive_key("access-token")


def create_access_token(subject: str | Any, session_id: str | Any, expires_delta: timedelta | None = None) -> str:
    """A short-lived access token for ``subject`` (a user id), valid only while session ``session_id`` is."""
    # Wall-clock time, not utcnow(): that helper keeps timestamps strictly increasing and can run slightly ahead.
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    claims = {"sub": str(subject), "sid": str(session_id), "typ": "access", "aud": TOKEN_AUDIENCE, "iat": now}
    return str(jwt.encode(claims | {"exp": expire}, _access_key(), algorithm=ALGORITHM))


def decode_access_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Return (user id, session id) from a valid access token. Raises ``jwt.PyJWTError`` or ``ValueError``."""
    payload = jwt.decode(
        token,
        _access_key(),
        algorithms=[ALGORITHM],
        audience=TOKEN_AUDIENCE,
        leeway=TOKEN_CLOCK_LEEWAY_SECONDS,
        options={"require": ["exp", "iat", "sub", "sid", "typ", "aud"]},
    )
    if payload.get("typ") != "access":
        raise ValueError("not an access token")
    return uuid.UUID(str(payload["sub"])), uuid.UUID(str(payload["sid"]))
