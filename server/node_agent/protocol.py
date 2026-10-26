"""Outbound client for worker protocol v1.

With the node's private key available, the client authenticates with short-lived node sessions: it asks for a
challenge (with its enrollment credential), signs it with the node key, and uses the session token it gets back,
renewing it before it expires. Without a key (or against an older control plane) it falls back to the enrollment
credential.
"""

import asyncio
import base64
import logging
import random
import time
from collections.abc import Callable

import httpx

from .config import PROTOCOL_VERSION, WORKER_VERSION

logger = logging.getLogger(__name__)


class CredentialRevoked(Exception):  # noqa: N818
    pass


SESSION_RENEW_BEFORE_SECONDS = 300


class ProtocolError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


def backoff(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    return min(cap, base * 2**attempt) * (0.5 + random.random() / 2)


class ControlPlaneClient:
    def __init__(
        self,
        base_url: str,
        node_id: str | None = None,
        credential: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        private_key=None,
        on_signing_key: Callable[[dict | None], object] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api = f"{self.base_url}/api/v1/worker"
        self.node_id = node_id
        self.credential = credential
        self.private_key = private_key
        self.on_signing_key = on_signing_key
        self.session_token: str | None = None
        self.session_expires = 0.0
        self._session_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=40.0), transport=transport)

    def _base_headers(self) -> dict[str, str]:
        return {"X-AgentMesh-Protocol": str(PROTOCOL_VERSION), "User-Agent": f"agentmesh-worker/{WORKER_VERSION}"}

    @property
    def headers(self) -> dict[str, str]:
        h = self._base_headers()
        bearer = self.session_token or self.credential
        if self.node_id and bearer:
            h["Authorization"] = f"Bearer {bearer}"
            h["X-AgentMesh-Node-Id"] = self.node_id
        return h

    async def ensure_session(self, force: bool = False) -> None:
        """Get or renew a node session when this worker holds its node key. 401 from the session endpoints means
        the enrollment credential or key is no longer accepted: the node was revoked."""
        if self.private_key is None or not (self.node_id and self.credential):
            return
        async with self._session_lock:
            if not force and self.session_token and time.time() < self.session_expires - SESSION_RENEW_BEFORE_SECONDS:
                return
            from .identity import sign_session_challenge

            enrollment = self._base_headers() | {
                "Authorization": f"Bearer {self.credential}",
                "X-AgentMesh-Node-Id": self.node_id,
            }
            resp = await self._client.post(f"{self.api}/session/challenge", json={}, headers=enrollment)
            if resp.status_code == 404:
                return  # control plane predates node sessions: keep using the credential
            self._raise_for(resp)
            challenge = resp.json()["challenge"]
            signature = sign_session_challenge(self.private_key, self.node_id, challenge)
            resp = await self._client.post(
                f"{self.api}/session",
                json={"challenge": challenge, "signature": base64.b64encode(signature).decode()},
                headers=enrollment,
            )
            self._raise_for(resp)
            data = resp.json()
            self.session_token = data["session_token"]
            self.session_expires = time.time() + float(data["expires_in"])
            if self.on_signing_key is not None:
                self.on_signing_key(data.get("command_signing_key"))
            logger.info("Node session established (valid %ss)", data["expires_in"])

    def _raise_for(self, resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise CredentialRevoked(resp.text[:200])
        if resp.status_code >= 400:
            raise ProtocolError(resp.status_code, resp.text[:300])

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict, *, retries: int = 0) -> dict:
        attempt = 0
        renewed = False
        while True:
            try:
                if path != "/enroll":
                    await self.ensure_session()
                resp = await self._client.post(f"{self.api}{path}", json=payload, headers=self.headers)
            except httpx.HTTPError as exc:
                if attempt >= retries:
                    raise ProtocolError(0, f"{type(exc).__name__}") from None
                await asyncio.sleep(backoff(attempt))
                attempt += 1
                continue
            if resp.status_code == 401 and self.session_token and not renewed:
                # The session expired or was ended: prove possession again. If that is refused, we are revoked.
                renewed = True
                self.session_token = None
                continue
            if resp.status_code == 401 and self.node_id:
                raise CredentialRevoked(resp.text[:200])
            if resp.status_code >= 500 and attempt < retries:
                await asyncio.sleep(backoff(attempt))
                attempt += 1
                continue
            if resp.status_code >= 400:
                try:
                    detail = resp.json().get("detail", resp.text)
                except ValueError:
                    detail = resp.text
                raise ProtocolError(resp.status_code, str(detail)[:500])
            return resp.json()

    async def enroll(self, payload: dict) -> dict:
        return await self._post("/enroll", payload)

    async def heartbeat(self, payload: dict) -> dict:
        return await self._post("/heartbeat", payload)

    async def whoami(self) -> dict:
        await self.ensure_session()
        resp = await self._client.get(f"{self.api}/whoami", headers=self.headers)
        if resp.status_code == 401:
            raise CredentialRevoked(resp.text[:200])
        if resp.status_code >= 400:
            raise ProtocolError(resp.status_code, resp.text[:300])
        return resp.json()

    async def disconnect(self) -> None:
        await self._post("/disconnect", {})

    async def poll(self, wait_seconds: int = 20, max_commands: int = 5) -> list[dict]:
        data = await self._post("/commands/poll", {"wait_seconds": wait_seconds, "max_commands": max_commands})
        return data.get("commands", [])

    async def ack(self, command_id: str, status: str, error: str | None = None, nonce: str | None = None) -> None:
        body = {"status": status, "error": error} | ({"nonce": nonce} if nonce else {})
        await self._post(f"/commands/{command_id}/ack", body, retries=5)

    async def report(
        self,
        deployment_id: str,
        state: str,
        message: str | None = None,
        error_code: str | None = None,
        model_digest: str | None = None,
    ) -> dict | None:
        payload = {
            "state": state,
            "message": (message or None) and message[:500],
            "error_code": error_code,
            "model_digest": model_digest,
        }
        try:
            return await self._post(f"/deployments/{deployment_id}/status", payload, retries=5)
        except ProtocolError as exc:
            if exc.status in (404, 409):
                # The control plane no longer wants this transition (e.g. stopped meanwhile). Not retryable.
                logger.info("Status %s for %s not applied: %s", state, deployment_id, exc.detail)
                return None
            raise

    def tunnel_url(self) -> str:
        return self.api.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/tunnel"
