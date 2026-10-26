"""Verification of signed command authorizations from the control plane (see app/core/signing.py).

The worker pins the control plane's Ed25519 public key when it enrolls (or, for workers enrolled before signing
existed, at its first heartbeat after upgrading) and from then on refuses any command whose authorization is
missing, signed by another key, altered, addressed to another node or command, expired, or already used. A new key is
accepted only when the pinned key endorses it (rotation).
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .state import _atomic_write, _read

logger = logging.getLogger(__name__)

COMMAND_CONTEXT = b"agentmesh-command-v1."
ENDORSEMENT_CONTEXT = b"agentmesh-command-key-v1."
CLOCK_SKEW_SECONDS = 60


class CommandRejected(Exception):  # noqa: N818
    pass


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()


def _key_id(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:16]


class KeyRing:
    """Pinned control-plane signing keys, kept with 0600 permissions next to the node credential."""

    def __init__(self, data_dir: Path):
        self.path = data_dir / "signing_keys.json"
        self.keys: dict[str, str] = _read(self.path, {}).get("keys", {})
        self._nonces: dict[str, float] = {}

    @property
    def pinned(self) -> bool:
        return bool(self.keys)

    def accept(self, info: dict | None) -> bool:
        """Pin the first key seen; afterwards add a key only if a pinned key endorsed it. Returns True when the
        offered key is (now) trusted."""
        if not info or not info.get("kid") or not info.get("public_key"):
            return False
        kid, raw = str(info["kid"]), _b64d(str(info["public_key"]))
        if len(raw) != 32 or _key_id(raw) != kid:
            logger.error("Ignoring malformed command signing key %s", kid)
            return False
        if kid in self.keys:
            return True
        if self.keys:
            endorser = self.keys.get(str(info.get("endorsed_by")))
            try:
                if endorser is None:
                    raise InvalidSignature
                Ed25519PublicKey.from_public_bytes(_b64d(endorser)).verify(
                    _b64d(str(info.get("endorsement", ""))), ENDORSEMENT_CONTEXT + kid.encode() + b"." + raw
                )
            except (InvalidSignature, ValueError):
                logger.error("Refusing command signing key %s: not endorsed by a pinned key", kid)
                return False
            logger.warning("Control plane rotated its command signing key to %s (endorsed)", kid)
        else:
            logger.info("Pinned control plane command signing key %s", kid)
        self.keys[kid] = str(info["public_key"])
        _atomic_write(self.path, {"keys": self.keys})
        return True

    def verify(self, cmd: dict, node_id: str, now: float | None = None) -> dict:
        """Return the claims of a valid authorization for ``cmd``; raise CommandRejected otherwise."""
        now = time.time() if now is None else now
        token = cmd.get("authorization")
        if not self.keys:
            raise CommandRejected("no pinned signing key")
        if not isinstance(token, str) or token.count(".") != 1:
            raise CommandRejected("missing or malformed authorization")
        body, sig = token.split(".")
        try:
            claims = json.loads(_b64d(body))
            key = self.keys.get(str(claims.get("kid")))
            if key is None:
                raise CommandRejected("signed by an unknown key")
            Ed25519PublicKey.from_public_bytes(_b64d(key)).verify(_b64d(sig), COMMAND_CONTEXT + body.encode())
        except (InvalidSignature, ValueError, AttributeError):
            raise CommandRejected("bad signature") from None
        expected = {
            "cmd": str(cmd.get("id")),
            "node": str(node_id),
            "type": cmd.get("type"),
            "dep": str(cmd["deployment_id"]) if cmd.get("deployment_id") else None,
        }
        for field, value in expected.items():
            if claims.get(field) != value:
                raise CommandRejected(f"authorization is for another {field}")
        digest = hashlib.sha256(_canonical(cmd.get("payload") or {})).hexdigest()
        if not hmac.compare_digest(str(claims.get("payload_sha256")), digest):
            raise CommandRejected("payload does not match its authorization")
        if not (claims.get("iat", 0) - CLOCK_SKEW_SECONDS <= now <= claims.get("exp", 0) + CLOCK_SKEW_SECONDS):
            raise CommandRejected("authorization expired")
        nonce = str(claims.get("nonce", ""))
        self._nonces = {n: exp for n, exp in self._nonces.items() if exp > now}
        if not nonce or nonce in self._nonces:
            raise CommandRejected("authorization already used")
        self._nonces[nonce] = float(claims["exp"]) + CLOCK_SKEW_SECONDS
        return dict(claims)
