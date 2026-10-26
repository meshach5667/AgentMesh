"""Purpose-separated keys.

Each use of server-side key material gets its own key, derived from ``SECRET_KEY`` with HKDF-SHA256 and a distinct
label, so a signature or MAC made for one purpose can never be accepted for another (a sponsored-view token as a
login token, say). Rotating ``SECRET_KEY`` rotates every derived key; see docs/security/INCIDENT_RESPONSE.md.
"""

from functools import lru_cache

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

# Every purpose in use. Adding one is a reviewed change, so labels are never reused by accident.
PURPOSES = frozenset({"access-token", "mfa-challenge", "sponsored-view", "command-signing", "data-encryption"})


@lru_cache(maxsize=32)
def _derive(secret: str, purpose: str, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=None, info=f"agentmesh/{purpose}/v1".encode()).derive(
        secret.encode()
    )


def derive_key(purpose: str, length: int = 32) -> bytes:
    if purpose not in PURPOSES:
        raise ValueError(f"Unknown key purpose {purpose!r}")
    return _derive(settings.SECRET_KEY, purpose, length)
