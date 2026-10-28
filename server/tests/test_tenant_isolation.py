"""Tenant isolation through the real API and database: one customer or provider never reads, changes, lists or
deletes another's resources, and another tenant's resources answer 404 (existence is not confirmed)."""

import uuid

import pytest

from app.documents import AiRun, Customer, NodeCommand
from app.services.tunnel import broker
from tests.test_gateway import FakeWorker


@pytest.fixture
async def alice_world(client, db, make_user, enroll_node, ollama_model):
    """Alice (customer) with a READY deployment on a node, an API key and an AI run; Bob is another customer."""
    node = await enroll_node()
    alice, alice_h = await make_user("customer")
    _, bob_h = await make_user("customer")
    dep = (await client.post("/api/v1/deployments", json={"model_id": str(ollama_model.id)}, headers=alice_h)).json()
    ready = await client.post(
        f"/api/v1/worker/deployments/{dep['id']}/status", json={"state": "READY"}, headers=node["headers"]
    )
    assert ready.status_code == 200, ready.text
    key = (await client.post("/api/v1/api-keys", json={"name": "alice"}, headers=alice_h)).json()
    customer = await db.find_one(Customer, {"user_id": alice.id})
    run = AiRun(customer_id=customer.id, user_id=alice.id, status="FAILED", request_text="private request", limits={})
    db.add(run)
    await db.commit()
    worker = FakeWorker(node["node_id"])
    await broker.register(worker.conn)
    yield {"alice": alice_h, "bob": bob_h, "dep": dep, "key": key, "run": run, "node": node, "worker": worker}
    broker.unregister(worker.conn)


async def test_customer_cannot_touch_another_customers_deployment(client, alice_world):
    w, bob = alice_world, alice_world["bob"]
    dep_id = w["dep"]["id"]
    for method, path in [
        ("GET", f"/api/v1/deployments/{dep_id}"),
        ("GET", f"/api/v1/deployments/{dep_id}/events"),
        ("POST", f"/api/v1/deployments/{dep_id}/stop"),
        ("POST", f"/api/v1/deployments/{dep_id}/restart"),
        ("DELETE", f"/api/v1/deployments/{dep_id}"),
        ("GET", f"/api/v1/usage/{dep_id}"),
    ]:
        resp = await client.request(method, path, headers=bob)
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}"
    assert all(d["id"] != dep_id for d in (await client.get("/api/v1/deployments", headers=bob)).json())
    # Still Alice's and still serving.
    assert (await client.get(f"/api/v1/deployments/{dep_id}", headers=w["alice"])).json()["status"] == "READY"


async def test_customer_cannot_call_another_customers_model(client, alice_world):
    w = alice_world
    url = f"/api/v1/deployments/{w['dep']['id']}/ollama/api/chat"
    body = {"messages": [{"role": "user", "content": "hi"}], "stream": False}
    bob_key = (await client.post("/api/v1/api-keys", json={"name": "bob"}, headers=w["bob"])).json()["key"]
    for headers in (w["bob"], {"Authorization": f"Bearer {bob_key}"}):
        resp = await client.post(url, json=body, headers=headers)
        assert resp.status_code == 404 and resp.json()["error"]["code"] == "deployment_not_found"
    assert w["worker"].received == []  # nothing reached Alice's node
    ok = await client.post(url, json=body, headers={"Authorization": f"Bearer {w['key']['key']}"})
    assert ok.status_code == 200


async def test_api_keys_and_ai_runs_are_private(client, alice_world):
    w, bob = alice_world, alice_world["bob"]
    assert (await client.delete(f"/api/v1/api-keys/{w['key']['id']}", headers=bob)).status_code == 404
    assert all(k["id"] != w["key"]["id"] for k in (await client.get("/api/v1/api-keys", headers=bob)).json())
    run_id = str(w["run"].id)
    for method, path in [
        ("GET", f"/api/v1/ai/deployments/{run_id}"),
        ("GET", f"/api/v1/ai/deployments/{run_id}/events"),
        ("POST", f"/api/v1/ai/deployments/{run_id}/cancel"),
    ]:
        assert (await client.request(method, path, headers=bob)).status_code == 404, path
    assert (await client.get("/api/v1/ai/deployments", headers=bob)).json() == []
    assert (await client.get(f"/api/v1/ai/deployments/{run_id}", headers=w["alice"])).status_code == 200


async def test_cost_estimates_are_scoped_to_the_caller(client, alice_world):
    w, bob = alice_world, alice_world["bob"]
    assert (await client.get("/api/v1/billing/estimates", headers=bob)).json() == []
    dep_id = w["dep"]["id"]
    assert (await client.get(f"/api/v1/billing/estimates?deployment_id={dep_id}", headers=bob)).json() == []
    for path in ("pricing", "attempts"):
        assert (await client.get(f"/api/v1/deployments/{dep_id}/{path}", headers=bob)).status_code == 404
    assert (await client.post(f"/api/v1/deployments/{dep_id}/retry", headers=bob)).status_code == 404
    assert (
        await client.patch(f"/api/v1/deployments/{dep_id}", json={"failover_policy": "manual"}, headers=bob)
    ).status_code == 404
    for scope in ("network", "provider"):
        assert (await client.get(f"/api/v1/billing/estimates?scope={scope}", headers=bob)).status_code == 403
        assert (await client.get(f"/api/v1/billing/estimates/summary?scope={scope}", headers=bob)).status_code == 403


async def test_provider_cannot_manage_or_impersonate_another_providers_node(client, db, alice_world, enroll_node):
    w = alice_world
    other = await enroll_node()
    victim = w["node"]["node_id"]
    for method, path, body in [
        ("GET", f"/api/v1/nodes/{victim}", None),
        ("PATCH", f"/api/v1/nodes/{victim}", {"accepting_workloads": False}),
        ("POST", f"/api/v1/nodes/{victim}/revoke", None),
    ]:
        resp = await client.request(method, path, json=body, headers=other["provider_headers"])
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}"

    # A node cannot report on, or take commands for, a deployment placed on another node.
    dep_id = w["dep"]["id"]
    resp = await client.post(
        f"/api/v1/worker/deployments/{dep_id}/status", json={"state": "FAILED"}, headers=other["headers"]
    )
    assert resp.status_code == 404
    cmd = NodeCommand(node_id=uuid.UUID(victim), deployment_id=uuid.UUID(dep_id), type="STOP", payload={})
    db.add(cmd)
    await db.commit()
    polled = await client.post(
        "/api/v1/worker/commands/poll", json={"max_commands": 10, "wait_seconds": 0}, headers=other["headers"]
    )
    assert all(c["id"] != str(cmd.id) for c in polled.json()["commands"])
    ack = await client.post(
        f"/api/v1/worker/commands/{cmd.id}/ack", json={"status": "succeeded"}, headers=other["headers"]
    )
    assert ack.status_code == 404
    # The node id header cannot be swapped to borrow another node's identity.
    forged = dict(other["headers"], **{"X-AgentMesh-Node-Id": victim})
    assert (await client.get("/api/v1/worker/whoami", headers=forged)).status_code == 401
