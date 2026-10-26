"""Ed25519 signatures on the commands the control plane sends to nodes (job authorizations).

A command authorization is ``<base64url(claims JSON)>.<base64url(signature)>``, signed over
``agentmesh-command-v1.<base64url(claims JSON)>``. Its claims bind it to one command lease: key id, command id,
node id, type, deployment id, the SHA-256 of the exact payload (and, readably, the model, digest and resource limits),
issue and expiry times and a fresh nonce. Workers verify it with a public key they pinned at enrollment, so they need
no signing material and a forged or altered command is refused even if someone can answer as the control plane.

The private key is ``COMMAND_SIGNING_KEY`` (base64 of a 32-byte Ed25519 seed) or, by default, a seed derived from
``SECRET_KEY`` for this purpose only. To rotate, move the current key to ``COMMAND_SIGNING_PREVIOUS_KEY`` and set a new
``COMMAND_SIGNING_KEY``: the previous key endorses the new one, so pinned workers accept it without re-enrolling.
"""

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.config import settings
from app.core.keys import derive_key

COMMAND_CONTEXT = b"agentmesh-command-v1."
ENDORSEMENT_CONTEXT = b"agentmesh-command-key-v1."


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


@lru_cache(maxsize=4)
def _key_from_seed(seed: bytes) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(seed)


def _current() -> Ed25519PrivateKey:
    seed = base64.b64decode(settings.COMMAND_SIGNING_KEY) if settings.COMMAND_SIGNING_KEY else None
    return _key_from_seed(seed or derive_key("command-signing"))


def _previous() -> Ed25519PrivateKey | None:
    if not settings.COMMAND_SIGNING_PREVIOUS_KEY:
        return None
    return _key_from_seed(base64.b64decode(settings.COMMAND_SIGNING_PREVIOUS_KEY))


def _raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(public_raw: bytes) -> str:
    return hashlib.sha256(public_raw).hexdigest()[:16]


def signing_key_info() -> dict[str, Any]:
    """The current public key as workers pin it, plus an endorsement by the previous key during a rotation."""
    raw = _raw_public(_current())
    info: dict[str, Any] = {"kid": key_id(raw), "public_key": b64url(raw)}
    previous = _previous()
    if previous is not None:
        info["endorsed_by"] = key_id(_raw_public(previous))
        info["endorsement"] = b64url(previous.sign(ENDORSEMENT_CONTEXT + info["kid"].encode() + b"." + raw))
    return info


def authorize_command(
    *, command_id: Any, node_id: Any, command_type: str, deployment_id: Any, payload: dict
) -> tuple[str, str, datetime]:
    """Sign one delivery (lease) of a command. Returns (authorization, nonce, expiry)."""
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=settings.COMMAND_AUTH_TTL_SECONDS)
    nonce = secrets.token_urlsafe(18)
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    raw = _raw_public(_current())
    claims = {
        "v": 1,
        "kid": key_id(raw),
        "cmd": str(command_id),
        "node": str(node_id),
        "type": command_type,
        "dep": str(deployment_id) if deployment_id else None,
        "payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "model": payload.get("model_tag"),
        "digest": (source or {}).get("sha256"),
        "limits": payload.get("resources"),
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "nonce": nonce,
    }
    body = b64url(canonical(claims))
    signature = _current().sign(COMMAND_CONTEXT + body.encode())
    return f"{body}.{b64url(signature)}", nonce, expires.replace(tzinfo=None)
