"""Node identity: quarantine, revocation latency, and re-authentication after outages, through the real worker API,
tunnel endpoint and database."""

import asyncio
import time
import uuid

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.v1.worker import tunnel
from app.core.config import settings
from app.documents import AuditLog, Deployment, Node, NodeCommand
from app.services.tunnel import broker

HEARTBEAT = {"worker_version": "1", "metrics": {}, "deployments": []}


class TunnelSocket:
    """A worker's WebSocket as the tunnel endpoint sees it: it stays open until the server closes it."""

    def __init__(self, node: dict):
        self.headers = {
            "authorization": node["headers"]["Authorization"],
            "x-agentmesh-node-id": node["node_id"],
            "x-agentmesh-protocol": "1",
        }
        self.accepted = asyncio.Event()
        self.closed = asyncio.Event()
        self.close_code: int | None = None

    async def accept(self):
        self.accepted.set()

    async def close(self, code: int = 1000):
        self.close_code = code
        self.closed.set()

    async def send_json(self, frame):
        pass

    async def receive_text(self) -> str:
        await self.closed.wait()
        raise WebSocketDisconnect(code=self.close_code or 1000)


async def _open_tunnel(node) -> tuple[TunnelSocket, asyncio.Task]:
    ws = TunnelSocket(node)
    task = asyncio.create_task(tunnel(ws))  # type: ignore[arg-type]
    done, _ = await asyncio.wait(
        {task, asyncio.create_task(ws.accepted.wait())}, timeout=5, return_when="FIRST_COMPLETED"
    )
    return ws, task


async def _ready_deployment(client, make_user, node, model) -> dict:
    _, customer = await make_user("customer")
    dep = (await client.post("/api/v1/deployments", json={"model_id": str(model.id)}, headers=customer)).json()
    ready = await client.post(
        f"/api/v1/worker/deployments/{dep['id']}/status", json={"state": "READY"}, headers=node["headers"]
    )
    assert ready.status_code == 200, ready.text
    return dep


async def test_operator_quarantine_cuts_a_node_off_at_once_and_is_reversible(
    client, db, make_user, enroll_node, ollama_model
):
    node = await enroll_node()
    dep = await _ready_deployment(client, make_user, node, ollama_model)
    ws, task = await _open_tunnel(node)
    assert ws.accepted.is_set() and broker.is_local(uuid.UUID(node["node_id"]))
    _, operator = await make_user("operator")
    url = f"/api/v1/admin/nodes/{node['node_id']}/quarantine"

    # Providers (even the owner) cannot quarantine or release; only staff can.
    assert (await client.post(url, json={"reason": "x" * 5}, headers=node["provider_headers"])).status_code == 403
    resp = await client.post(url, json={"reason": "Suspected tampering"}, headers=operator)
    assert resp.status_code == 200 and resp.json()["status"] == "QUARANTINED"

    await asyncio.wait_for(ws.closed.wait(), timeout=2)  # tunnel closed immediately, not at the next check
    await asyncio.wait_for(task, timeout=2)
    for method, path in [("POST", "/api/v1/worker/heartbeat"), ("GET", "/api/v1/worker/whoami")]:
        body = HEARTBEAT if method == "POST" else None
        r = await client.request(method, path, json=body, headers=node["headers"])
        assert r.status_code == 403, path
    poll = await client.post(
        "/api/v1/worker/commands/poll", json={"max_commands": 5, "wait_seconds": 0}, headers=node["headers"]
    )
    assert poll.status_code == 403
    db.expire_all()
    moved = await db.get(Deployment, uuid.UUID(dep["id"]))
    assert moved.node_id != uuid.UUID(node["node_id"]) or moved.status in ("FAILED", "REQUESTED", "SCHEDULED")
    assert (await db.find_one(AuditLog, {"action": "node.quarantined"})).details["reason"] == "Suspected tampering"
    # Reconnecting is refused while quarantined.
    ws2, task2 = await _open_tunnel(node)
    await asyncio.wait_for(task2, timeout=2)
    assert not ws2.accepted.is_set() and ws2.close_code == 4401

    released = await client.post(f"/api/v1/admin/nodes/{node['node_id']}/release", headers=operator)
    assert released.json()["status"] == "OFFLINE"
    beat = await client.post(
        "/api/v1/worker/heartbeat",
        json={"worker_version": "1", "metrics": {}, "deployments": []},
        headers=node["headers"],
    )
    assert beat.status_code == 200
    assert (await db.find_one(AuditLog, {"action": "node.released"})) is not None


async def test_revoked_node_loses_its_tunnel_within_the_window_even_if_the_disconnect_is_lost(
    client, db, enroll_node, monkeypatch
):
    monkeypatch.setattr(settings, "TUNNEL_REVALIDATE_SECONDS", 1)
    node = await enroll_node()
    ws, task = await _open_tunnel(node)
    assert ws.accepted.is_set()
    # Revoke in the database only, as if the close message to this replica never arrived.
    await db.update_one(
        Node, {"_id": uuid.UUID(node["node_id"])}, {"$set": {"status": "REVOKED", "api_key_hash": None}}
    )
    await db.commit()
    started = time.monotonic()
    await asyncio.wait_for(ws.closed.wait(), timeout=settings.TUNNEL_REVALIDATE_SECONDS + 2)
    assert time.monotonic() - started <= settings.TUNNEL_REVALIDATE_SECONDS + 1
    assert ws.close_code == 4401
    await asyncio.wait_for(task, timeout=2)
    assert not broker.is_local(uuid.UUID(node["node_id"]))


async def test_rekeyed_node_loses_its_tunnel(client, db, enroll_node, monkeypatch):
    monkeypatch.setattr(settings, "TUNNEL_REVALIDATE_SECONDS", 1)
    node = await enroll_node()
    ws, task = await _open_tunnel(node)
    await db.update_one(Node, {"_id": uuid.UUID(node["node_id"])}, {"$set": {"api_key_hash": "sha256$" + "0" * 64}})
    await db.commit()
    await asyncio.wait_for(ws.closed.wait(), timeout=4)
    await asyncio.wait_for(task, timeout=2)


async def test_default_window_is_documented_and_bounded():
    assert 1 <= settings.TUNNEL_REVALIDATE_SECONDS <= 30
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError, match="TUNNEL_REVALIDATE_SECONDS"):
        Settings(TUNNEL_REVALIDATE_SECONDS=120, ENVIRONMENT="test", _env_file=None)


async def test_reconnection_after_an_outage_is_fully_reauthenticated(client, db, make_user, enroll_node):
    node = await enroll_node()
    ws, task = await _open_tunnel(node)
    assert ws.accepted.is_set()
    # Outage: the worker disconnects; meanwhile its provider revokes it.
    await ws.close(1006)
    await asyncio.wait_for(task, timeout=2)
    revoke = await client.post(f"/api/v1/nodes/{node['node_id']}/revoke", headers=node["provider_headers"])
    assert revoke.status_code == 200
    ws2, task2 = await _open_tunnel(node)
    await asyncio.wait_for(task2, timeout=2)
    assert not ws2.accepted.is_set() and ws2.close_code == 4401
    beat = await client.post(
        "/api/v1/worker/heartbeat",
        json={"worker_version": "1", "metrics": {}, "deployments": []},
        headers=node["headers"],
    )
    assert beat.status_code == 401


async def test_a_long_poll_cannot_lease_work_after_revocation(client, db, enroll_node, monkeypatch):
    node = await enroll_node()
    node_id = uuid.UUID(node["node_id"])

    async def revoke_then_queue_work():
        await asyncio.sleep(1.2)
        await db.update_one(Node, {"_id": node_id}, {"$set": {"status": "REVOKED", "api_key_hash": None}})
        db.add(NodeCommand(node_id=node_id, type="STOP", payload={}))
        await db.commit()

    background = asyncio.create_task(revoke_then_queue_work())
    poll = await client.post(
        "/api/v1/worker/commands/poll", json={"max_commands": 5, "wait_seconds": 4}, headers=node["headers"]
    )
    await background
    assert poll.status_code == 401
    leased = await db.find(NodeCommand, {"node_id": node_id, "status": "LEASED"})
    assert leased == []


@pytest.mark.parametrize("auth", ["enrollment_credential", "node_session"])
async def test_a_healthy_long_poll_waits_and_picks_up_work_that_arrives(client, db, enroll_node, auth):
    """Regression: an inverted re-check refused every long poll after its first second, so idle workers thought
    they had been revoked and shut down."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    from node_agent.identity import get_public_key_pem
    from tests.test_node_sessions import _session, _with

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    node = await enroll_node(public_key=get_public_key_pem(key.public_key()))
    node["private_key"] = key
    headers = node["headers"]
    if auth == "node_session":
        headers = _with(node, (await _session(client, node)).json()["session_token"])
    node_id = uuid.UUID(node["node_id"])

    started = time.monotonic()
    idle = await client.post(
        "/api/v1/worker/commands/poll", json={"max_commands": 5, "wait_seconds": 2}, headers=headers
    )
    assert idle.status_code == 200, idle.text
    assert idle.json()["commands"] == [] and time.monotonic() - started >= 1.5

    async def queue_work():
        await asyncio.sleep(1.2)
        db.add(NodeCommand(node_id=node_id, type="STOP", payload={}))
        await db.commit()

    background = asyncio.create_task(queue_work())
    busy = await client.post(
        "/api/v1/worker/commands/poll", json={"max_commands": 5, "wait_seconds": 4}, headers=headers
    )
    await background
    assert busy.status_code == 200 and len(busy.json()["commands"]) == 1


async def test_a_long_poll_is_cut_off_by_quarantine(client, db, enroll_node):
    node = await enroll_node()
    node_id = uuid.UUID(node["node_id"])

    async def quarantine():
        await asyncio.sleep(1.2)
        await db.update_one(Node, {"_id": node_id}, {"$set": {"status": "QUARANTINED"}})
        db.add(NodeCommand(node_id=node_id, type="STOP", payload={}))
        await db.commit()

    background = asyncio.create_task(quarantine())
    poll = await client.post(
        "/api/v1/worker/commands/poll", json={"max_commands": 5, "wait_seconds": 4}, headers=node["headers"]
    )
    await background
    assert poll.status_code == 403
    assert await db.find(NodeCommand, {"node_id": node_id, "status": "LEASED"}) == []


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "Bearer am_node_wrong", "X-AgentMesh-Protocol": "1"},
        {"X-AgentMesh-Protocol": "1"},
        {"Authorization": "Basic abc", "X-AgentMesh-Protocol": "1"},
    ],
)
async def test_wrong_or_missing_node_credentials_are_rejected(client, enroll_node, headers):
    node = await enroll_node()
    resp = await client.get("/api/v1/worker/whoami", headers=headers | {"X-AgentMesh-Node-Id": node["node_id"]})
    assert resp.status_code == 401
