"""Node sessions by proof of possession (G-08) and signed command authorizations (G-11), through the real worker API,
the real agent client and verifier, and the database."""

import base64
import time
import uuid
from datetime import datetime

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core import signing
from app.core.config import settings
from app.documents import Node, NodeCommand, NodeSession
from app.main import app
from node_agent.command_auth import CommandRejected, KeyRing
from node_agent.identity import get_public_key_pem, sign_session_challenge
from node_agent.protocol import ControlPlaneClient, CredentialRevoked

HEARTBEAT = {"worker_version": "1", "metrics": {}, "deployments": []}


@pytest.fixture
async def keyed_node(enroll_node):
    """A node enrolled with an RSA key generated on the node, as the real agent does."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    node = await enroll_node(public_key=get_public_key_pem(key.public_key()))
    node["private_key"] = key
    return node


async def _session(client, node, key=None) -> httpx.Response:
    chal = await client.post("/api/v1/worker/session/challenge", json={}, headers=node["headers"])
    assert chal.status_code == 200, chal.text
    challenge = chal.json()["challenge"]
    sig = sign_session_challenge(key or node["private_key"], node["node_id"], challenge)
    return await client.post(
        "/api/v1/worker/session",
        json={"challenge": challenge, "signature": base64.b64encode(sig).decode()},
        headers=node["headers"],
    )


def _with(node, token) -> dict:
    return dict(node["headers"], Authorization=f"Bearer {token}")


async def test_session_needs_the_node_key_and_works_once_per_challenge(client, keyed_node):
    node = keyed_node
    ok = await _session(client, node)
    assert ok.status_code == 200, ok.text
    token = ok.json()["session_token"]
    assert token.startswith("am_ns_") and ok.json()["expires_in"] == settings.NODE_SESSION_TTL_MINUTES * 60
    offered = ok.json()["command_signing_key"]
    assert {k: offered[k] for k in ("kid", "public_key")} == signing.signing_key_info()
    assert (
        await client.post("/api/v1/worker/heartbeat", json=HEARTBEAT, headers=_with(node, token))
    ).status_code == 200

    # The enrollment credential alone, with another key, gets nothing.
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert (await _session(client, node, key=stranger)).status_code == 401
    # A challenge cannot be used twice.
    chal = (await client.post("/api/v1/worker/session/challenge", json={}, headers=node["headers"])).json()
    sig = base64.b64encode(sign_session_challenge(node["private_key"], node["node_id"], chal["challenge"])).decode()
    body = {"challenge": chal["challenge"], "signature": sig}
    assert (await client.post("/api/v1/worker/session", json=body, headers=node["headers"])).status_code == 200
    assert (await client.post("/api/v1/worker/session", json=body, headers=node["headers"])).status_code == 401
    # A session token cannot be used to mint further sessions: that needs the enrollment credential.
    again = await client.post("/api/v1/worker/session/challenge", json={}, headers=_with(node, token))
    assert again.status_code == 401


async def test_node_without_a_registered_key_cannot_get_a_session(client, enroll_node):
    node = await enroll_node()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert (await _session(client, node, key=key)).status_code == 401


async def test_expired_challenge_and_expired_session_are_refused(client, db, keyed_node, monkeypatch):
    node = keyed_node
    token = (await _session(client, node)).json()["session_token"]
    await db.update_many(NodeSession, {}, {"$set": {"expires_at": datetime(2020, 1, 1)}})
    await db.commit()
    resp = await client.post("/api/v1/worker/heartbeat", json=HEARTBEAT, headers=_with(node, token))
    assert resp.status_code == 401 and "expired" in resp.text

    from app.documents import NodeChallenge

    chal = (await client.post("/api/v1/worker/session/challenge", json={}, headers=node["headers"])).json()
    await db.update_many(NodeChallenge, {}, {"$set": {"expires_at": datetime(2020, 1, 1)}})
    await db.commit()
    sig = base64.b64encode(sign_session_challenge(node["private_key"], node["node_id"], chal["challenge"])).decode()
    late = await client.post(
        "/api/v1/worker/session", json={"challenge": chal["challenge"], "signature": sig}, headers=node["headers"]
    )
    assert late.status_code == 401


async def test_with_legacy_mode_off_only_sessions_authenticate(client, keyed_node, monkeypatch):
    node = keyed_node
    monkeypatch.setattr(settings, "ALLOW_LEGACY_NODE_CREDENTIALS", False)
    legacy = await client.post("/api/v1/worker/heartbeat", json=HEARTBEAT, headers=node["headers"])
    assert legacy.status_code == 401 and "session required" in legacy.text
    token = (await _session(client, node)).json()["session_token"]
    assert (
        await client.post("/api/v1/worker/heartbeat", json=HEARTBEAT, headers=_with(node, token))
    ).status_code == 200


@pytest.mark.parametrize("action", ["revoke", "quarantine"])
async def test_revocation_and_quarantine_end_node_sessions(client, make_user, keyed_node, action):
    node = keyed_node
    token = (await _session(client, node)).json()["session_token"]
    if action == "revoke":
        resp = await client.post(f"/api/v1/nodes/{node['node_id']}/revoke", headers=node["provider_headers"])
    else:
        _, operator = await make_user("operator")
        resp = await client.post(
            f"/api/v1/admin/nodes/{node['node_id']}/quarantine", json={"reason": "investigating"}, headers=operator
        )
    assert resp.status_code == 200
    beat = await client.post("/api/v1/worker/heartbeat", json=HEARTBEAT, headers=_with(node, token))
    assert beat.status_code in (401, 403)


async def test_tunnel_close_reason_distinguishes_revoked_blocked_and_expired(client, db, keyed_node):
    from app.core.security import hash_secret
    from app.services.worker_service import still_authorized

    node = keyed_node
    node_id = uuid.UUID(node["node_id"])
    token = (await _session(client, node)).json()["session_token"]
    assert await still_authorized(node_id, hash_secret(token)) is None
    await db.update_many(NodeSession, {}, {"$set": {"expires_at": datetime(2020, 1, 1)}})
    await db.commit()
    assert await still_authorized(node_id, hash_secret(token)) == "session_expired"
    await db.update_one(Node, {"_id": node_id}, {"$set": {"status": "QUARANTINED"}})
    await db.commit()
    assert await still_authorized(node_id, hash_secret(token)) == "blocked"
    await db.update_one(Node, {"_id": node_id}, {"$set": {"status": "REVOKED"}})
    await db.commit()
    assert await still_authorized(node_id, hash_secret(token)) == "revoked"


# --- the real agent client against the real control plane -----------------------------------------------------


def _agent(node, keys: KeyRing) -> ControlPlaneClient:
    return ControlPlaneClient(
        "http://test",
        node["node_id"],
        node["credential"],
        transport=httpx.ASGITransport(app=app),
        private_key=node["private_key"],
        on_signing_key=keys.accept,
    )


async def test_agent_uses_sessions_verifies_signed_commands_and_acks_with_the_nonce(
    client, db, keyed_node, tmp_path, monkeypatch
):
    node = keyed_node
    keys = KeyRing(tmp_path)
    assert keys.accept(node["signing_key"])  # pinned at enrollment
    agent = _agent(node, keys)
    try:
        await agent.heartbeat(HEARTBEAT)
        assert agent.session_token and agent.headers["Authorization"] == f"Bearer {agent.session_token}"
        cmd = NodeCommand(node_id=uuid.UUID(node["node_id"]), type="STOP", payload={"deployment_id": None})
        db.add(cmd)
        await db.commit()
        [polled] = await agent.poll(wait_seconds=0)
        claims = keys.verify(polled, node["node_id"])
        assert claims["cmd"] == str(cmd.id) and claims["node"] == node["node_id"]
        with pytest.raises(CommandRejected, match="already used"):
            keys.verify(polled, node["node_id"])  # replayed delivery

        # Lease lapses and the command is delivered again: a new authorization, and the old nonce is now stale.
        await db.update_one(NodeCommand, {"_id": cmd.id}, {"$set": {"lease_expires_at": datetime(2020, 1, 1)}})
        await db.commit()
        [again] = await agent.poll(wait_seconds=0)
        fresh = keys.verify(again, node["node_id"])
        assert fresh["nonce"] != claims["nonce"]
        stale = await client.post(
            f"/api/v1/worker/commands/{cmd.id}/ack",
            json={"status": "succeeded", "nonce": claims["nonce"]},
            headers=node["headers"],
        )
        assert stale.status_code == 409
        await agent.ack(str(cmd.id), "succeeded", nonce=fresh["nonce"])
        db.expire_all()
        assert (await db.get(NodeCommand, cmd.id)).status == "SUCCEEDED"

        # Session ended server-side: the agent proves possession again transparently.
        old = agent.session_token
        await db.update_many(NodeSession, {}, {"$set": {"revoked_at": datetime(2026, 10, 26)}})
        await db.commit()
        await agent.heartbeat(HEARTBEAT)
        assert agent.session_token != old

        # Revoked: renewal is refused and the agent reports it.
        await client.post(f"/api/v1/nodes/{node['node_id']}/revoke", headers=node["provider_headers"])
        with pytest.raises(CredentialRevoked):
            await agent.heartbeat(HEARTBEAT)
    finally:
        await agent.close()


# --- authorization verification on the worker -----------------------------------------------------------------

PAYLOAD = {
    "deployment_id": "11111111-2222-3333-4444-555555555555",
    "runtime": "ollama",
    "model_tag": "qwen2.5:0.5b",
    "resources": {"cpu_cores": 1, "ram_mb": 512, "disk_mb": 0, "vram_mb": 0, "gpu": False},
}


def _cmd(node="node-1", cmd_id="c1", payload=None, **over):
    payload = payload or PAYLOAD
    auth, _, _ = signing.authorize_command(
        command_id=cmd_id, node_id=node, command_type="DEPLOY", deployment_id=payload["deployment_id"], payload=payload
    )
    return {
        "id": cmd_id,
        "type": "DEPLOY",
        "deployment_id": payload["deployment_id"],
        "payload": payload,
        "authorization": auth,
    } | over


@pytest.fixture
def ring(tmp_path):
    keys = KeyRing(tmp_path)
    keys.accept(signing.signing_key_info())
    return keys


def test_valid_authorization_is_accepted_and_binds_model_and_limits(ring):
    claims = ring.verify(_cmd(), "node-1")
    assert claims["model"] == "qwen2.5:0.5b" and claims["limits"]["ram_mb"] == 512 and claims["kid"]


@pytest.mark.parametrize(
    ("case", "mutate", "reason"),
    [
        ("modified payload", lambda c: c | {"payload": PAYLOAD | {"model_tag": "evil:latest"}}, "payload"),
        (
            "raised limits",
            lambda c: c | {"payload": PAYLOAD | {"resources": {**PAYLOAD["resources"], "ram_mb": 99999}}},
            "payload",
        ),
        ("other command id", lambda c: c | {"id": "c2"}, "cmd"),
        ("other type", lambda c: c | {"type": "STOP"}, "type"),
        ("other deployment", lambda c: c | {"deployment_id": str(uuid.uuid4())}, "dep"),
        ("no authorization", lambda c: {k: v for k, v in c.items() if k != "authorization"}, "missing"),
        ("garbage", lambda c: c | {"authorization": "abc"}, "malformed"),
        ("bad signature", lambda c: c | {"authorization": c["authorization"][:-6] + "AAAAAA"}, "signature"),
    ],
)
def test_tampered_or_misbound_authorizations_are_refused(ring, case, mutate, reason):
    with pytest.raises(CommandRejected, match=reason):
        ring.verify(mutate(_cmd()), "node-1")


def test_authorization_for_another_node_is_refused(ring):
    with pytest.raises(CommandRejected, match="node"):
        ring.verify(_cmd(node="node-2"), "node-1")


def test_expired_authorization_is_refused(ring):
    with pytest.raises(CommandRejected, match="expired"):
        ring.verify(_cmd(), "node-1", now=time.time() + settings.COMMAND_AUTH_TTL_SECONDS + 120)


def test_signature_by_an_unpinned_key_is_refused(tmp_path, monkeypatch):
    stranger = KeyRing(tmp_path / "other")
    stranger.accept(signing.signing_key_info())
    monkeypatch.setattr(settings, "COMMAND_SIGNING_KEY", base64.b64encode(b"x" * 32).decode())
    forged = _cmd()  # signed by a key the ring never pinned and nobody endorsed
    with pytest.raises(CommandRejected, match="unknown key"):
        stranger.verify(forged, "node-1")
    assert stranger.accept(signing.signing_key_info()) is False  # an unendorsed new key is not pinned


def test_rotation_is_accepted_only_when_endorsed_by_the_pinned_key(tmp_path, monkeypatch):
    old_seed, new_seed = base64.b64encode(b"o" * 32).decode(), base64.b64encode(b"n" * 32).decode()
    monkeypatch.setattr(settings, "COMMAND_SIGNING_KEY", old_seed)
    ring = KeyRing(tmp_path)
    ring.accept(signing.signing_key_info())
    monkeypatch.setattr(settings, "COMMAND_SIGNING_KEY", new_seed)
    monkeypatch.setattr(settings, "COMMAND_SIGNING_PREVIOUS_KEY", old_seed)
    assert ring.accept(signing.signing_key_info()) is True
    assert ring.verify(_cmd(), "node-1")["kid"] == signing.signing_key_info()["kid"]
    assert KeyRing(tmp_path).pinned  # persisted
    # A forged endorsement is refused.
    forged = signing.signing_key_info() | {"kid": "0" * 16}
    assert KeyRing(tmp_path / "fresh").accept(forged) is False


async def test_worker_does_not_act_on_a_tampered_command(tmp_path):
    from node_agent.config import WorkerSettings
    from node_agent.worker import Worker
    from tests.test_node_agent.test_worker import FakeClient, FakeRuntime

    runtime = FakeRuntime()
    w = Worker(
        WorkerSettings(DATA_DIR=str(tmp_path), CONTROL_PLANE_URL="http://localhost:1"),
        runtime=runtime,
        client=FakeClient(),
    )
    w.keys.accept(signing.signing_key_info())
    await w.handle_command(_cmd() | {"payload": PAYLOAD | {"model_tag": "evil:latest"}})
    assert w.workloads == {} and w.client.acks == [("c1", "failed")]
    assert w.client.ack_errors[0].startswith("COMMAND_AUTH_INVALID")
    # Without a pinned key nothing is executed either (fail closed).
    w2 = Worker(
        WorkerSettings(DATA_DIR=str(tmp_path / "unpinned"), CONTROL_PLANE_URL="http://localhost:1"),
        runtime=FakeRuntime(),
        client=FakeClient(),
    )
    await w2.handle_command(_cmd())
    assert w2.workloads == {} and w2.client.acks == [("c1", "failed")]
