"""Act as an authenticator app in tests."""

import base64
import time

from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives.twofactor.totp import TOTP


def totp_code(secret_b32: str, at: float | None = None) -> str:
    seed = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8))
    return TOTP(seed, 6, SHA1(), 30).generate(time.time() if at is None else at).decode()


async def enroll_mfa(client, headers) -> str:
    """Turn on MFA for the signed-in account; returns the base32 secret."""
    setup = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    enabled = await client.post("/api/v1/auth/mfa/enable", json={"code": totp_code(secret)}, headers=headers)
    assert enabled.status_code == 204, enabled.text
    return secret
