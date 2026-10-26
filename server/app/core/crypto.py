"""Authenticated encryption (AES-256-GCM, ``cryptography``) for small secrets kept in the database, such as MFA
seeds. Each value is bound to a context string (e.g. the owning user) as associated data, so a ciphertext copied
onto another record does not decrypt.

The key is ``DATA_ENCRYPTION_KEY`` when set (base64, 32 bytes), otherwise one derived from ``SECRET_KEY`` for this
purpose only. Either way it lives in the environment, never next to the data. Ciphertexts name their key id, so
values written under the derived key stay readable after a dedicated key is configured.
"""

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.core.keys import derive_key

PREFIX = "aesgcm:v1"


def _keys() -> dict[str, bytes]:
    keys = {"derived": derive_key("data-encryption")}
    if settings.DATA_ENCRYPTION_KEY:
        keys["dek1"] = base64.b64decode(settings.DATA_ENCRYPTION_KEY)
    return keys


def encrypt(plaintext: bytes, context: str) -> str:
    kid = "dek1" if settings.DATA_ENCRYPTION_KEY else "derived"
    nonce = os.urandom(12)
    sealed = AESGCM(_keys()[kid]).encrypt(nonce, plaintext, context.encode())
    return f"{PREFIX}:{kid}:{base64.b64encode(nonce + sealed).decode()}"


def decrypt(value: str, context: str) -> bytes:
    """Raises ValueError for anything that is not an intact ciphertext for this context under a known key."""
    try:
        prefix, version, kid, blob = value.split(":", 3)
        raw = base64.b64decode(blob, validate=True)
        key = _keys()[kid]
    except (ValueError, KeyError, binascii.Error):
        raise ValueError("Unreadable encrypted value") from None
    if f"{prefix}:{version}" != PREFIX or len(raw) < 12 + 16:
        raise ValueError("Unreadable encrypted value")
    try:
        return AESGCM(key).decrypt(raw[:12], raw[12:], context.encode())
    except InvalidTag:
        raise ValueError("Encrypted value failed authentication") from None
