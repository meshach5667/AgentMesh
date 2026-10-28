"""Planned moves (make-before-break): a serving deployment is moved off a node that is going away without an
interruption. The replacement starts first, traffic switches only when it is READY, and the old copy is stopped after
MIGRATION_DRAIN_SECONDS so requests in flight there can finish. A failed replacement changes nothing."""

import uuid
from datetime import timedelta

from app.background import monitors
from app.core.config import settings
from app.core.timeutil import utcnow
from app.documents import Deployment, DeploymentAttempt, DeploymentEvent, Node, NodeCommand, ResourceReservation
from app.services.cost_service import ready_intervals


async def _deploy(client, headers, model, **body):
    resp = await client.post("/api/v1/deployments", json={"model_id": str(model.id), **body}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _report(client, node, dep_id, state, **extra):
    return await client.post(
        f"/api/v1/worker/deployments/{dep_id}/status", json={"state": state, **extra}, headers=node["headers"]
    )


async def _poll(client, node):
    resp = await client.post("/api/v1/worker/commands/poll", json={"wait_seconds": 0}, headers=node["headers"])
    return resp.json()["commands"]


async def _dep(db, dep_id) -> Deployment:
    db.expire_all()
    return await db.get(Deployment, uuid.UUID(str(dep_id)))


async def _serving_on_a(client, make_user, enroll_node, model):
    _, provider = await make_user("provider")
    a = await enroll_node(provider=provider, ram_mb=8192)
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, model)
    assert dep["node_id"] == a["node_id"]
    await _poll(client, a)  # A picks up its DEPLOY, as a real worker would
    await _report(client, a, dep["id"], "READY")
    b = await enroll_node(provider=provider, ram_mb=4096)
    return provider, a, b, customer, dep


async def test_a_planned_move_starts_the_replacement_first_and_switches_without_a_gap(
    client, db, make_user, enroll_node, ollama_model
):
    provider, a, b, customer, dep = await _serving_on_a(client, make_user, enroll_node, ollama_model)
    resp = await client.post(f"/api/v1/nodes/{a['node_id']}/evacuate", headers=provider)
    assert resp.json() == {"moving": 1, "staying": 0}

    moving = await _dep(db, dep["id"])
    assert moving.status == "READY" and moving.node_id == uuid.UUID(a["node_id"])  # still serving on A
    assert moving.migrating_node_id == uuid.UUID(b["node_id"])
    assert await db.count(ResourceReservation, {"deployment_id": moving.id, "status": "STANDBY"}) == 1
    (cmd,) = await _poll(client, b)
    assert cmd["type"] == "DEPLOY" and cmd["payload"]["attempt_id"] == str(moving.migrating_attempt_id)
    standby_attempt = cmd["payload"]["attempt_id"]

    # The replacement warms up; its heartbeat is not told to stop it, and A keeps answering.
    hb = await client.post(
        "/api/v1/worker/heartbeat",
        json={
            "worker_version": "t",
            "deployments": [{"deployment_id": dep["id"], "state": "provisioning", "healthy": False}],
        },
        headers=b["headers"],
    )
    assert hb.json()["stop_deployments"] == []
    assert (await _report(client, b, dep["id"], "PROVISIONING", attempt_id=standby_attempt)).status_code == 200
    assert (await _dep(db, dep["id"])).node_id == uuid.UUID(a["node_id"])

    # Ready: traffic switches to B; A's attempt is superseded and A is stopped only after the drain period.
    assert (await _report(client, b, dep["id"], "READY", attempt_id=standby_attempt)).status_code == 200
    done = await _dep(db, dep["id"])
    assert done.status == "READY" and done.node_id == uuid.UUID(b["node_id"]) and done.migrating_attempt_id is None
    old, new = await db.find(DeploymentAttempt, {"deployment_id": done.id}, sort=[("number", 1)])
    assert (old.active, old.outcome) == (False, "superseded") and (new.active, new.state) == (True, "running")
    reservations = {r.node_id: r.status for r in await db.find(ResourceReservation, {"deployment_id": done.id})}
    assert reservations == {uuid.UUID(a["node_id"]): "RELEASED", uuid.UUID(b["node_id"]): "ACTIVE"}
    assert await _poll(client, a) == []  # the STOP for A waits so in-flight requests can finish
    stop = await db.find_one(NodeCommand, {"node_id": uuid.UUID(a["node_id"]), "type": "STOP"})
    assert stop.not_before > utcnow() + timedelta(seconds=settings.MIGRATION_DRAIN_SECONDS - 10)
    await db.update_one(NodeCommand, {"_id": stop.id}, {"$set": {"not_before": utcnow() - timedelta(seconds=1)}})
    await db.commit()
    assert [c["type"] for c in await _poll(client, a)] == ["STOP"]

    # READY time is attributed to A until the switch and to B after it; no gap, no overlap.
    events = await db.find(
        DeploymentEvent, {"deployment_id": done.id, "to_status": {"$ne": None}}, sort=[("created_at", 1)]
    )
    intervals = ready_intervals(events, utcnow(), done.node_id)
    assert [i.node_id for i in intervals] == [uuid.UUID(a["node_id"]), uuid.UUID(b["node_id"])]
    assert intervals[0].end == intervals[1].start
    kinds = [e.kind for e in await db.find(DeploymentEvent, {"deployment_id": done.id}, sort=[("created_at", 1)])]
    assert "migration_started" in kinds and "migrated" in kinds


async def test_a_failed_replacement_cancels_the_move_and_nothing_changes(
    client, db, make_user, enroll_node, ollama_model
):
    provider, a, b, customer, dep = await _serving_on_a(client, make_user, enroll_node, ollama_model)
    await client.post(f"/api/v1/nodes/{a['node_id']}/evacuate", headers=provider)
    (cmd,) = await _poll(client, b)
    await _report(
        client, b, dep["id"], "FAILED", error_code="INSUFFICIENT_MEMORY", attempt_id=cmd["payload"]["attempt_id"]
    )
    kept = await _dep(db, dep["id"])
    assert kept.status == "READY" and kept.node_id == uuid.UUID(a["node_id"]) and kept.migrating_attempt_id is None
    assert await db.count(ResourceReservation, {"deployment_id": kept.id, "status": "STANDBY"}) == 0
    node_b = await db.get(Node, uuid.UUID(b["node_id"]))
    assert node_b.reserved_ram_mb == 0
    assert await db.find_one(DeploymentEvent, {"deployment_id": kept.id, "kind": "migration_failed"}) is not None


async def test_a_replacement_that_goes_offline_cancels_the_move(client, db, make_user, enroll_node, ollama_model):
    provider, a, b, customer, dep = await _serving_on_a(client, make_user, enroll_node, ollama_model)
    await client.post(f"/api/v1/nodes/{a['node_id']}/evacuate", headers=provider)
    await db.update_one(
        Node, {"_id": uuid.UUID(b["node_id"])}, {"$set": {"last_heartbeat": utcnow() - timedelta(seconds=600)}}
    )
    await db.commit()
    await monitors.run_stale_nodes()
    kept = await _dep(db, dep["id"])
    assert kept.status == "READY" and kept.node_id == uuid.UUID(a["node_id"]) and kept.migrating_node_id is None


async def test_draining_a_worker_moves_its_deployments_once(client, db, make_user, enroll_node, ollama_model):
    provider, a, b, customer, dep = await _serving_on_a(client, make_user, enroll_node, ollama_model)
    drain = {"worker_version": "t", "available": False, "unavailable_reason": "draining", "deployments": []}
    for _ in range(3):
        await client.post("/api/v1/worker/heartbeat", json=drain, headers=a["headers"])
    moving = await _dep(db, dep["id"])
    assert moving.migrating_node_id == uuid.UUID(b["node_id"])
    assert await db.count(DeploymentAttempt, {"deployment_id": moving.id}) == 2  # one move, not one per heartbeat


async def test_without_a_replacement_or_with_manual_failover_the_deployment_stays(
    client, db, make_user, enroll_node, ollama_model
):
    _, provider = await make_user("provider")
    a = await enroll_node(provider=provider)
    _, customer = await make_user("customer")
    alone = await _deploy(client, customer, ollama_model)
    await _report(client, a, alone["id"], "READY")
    assert (await client.post(f"/api/v1/nodes/{a['node_id']}/evacuate", headers=provider)).json() == {
        "moving": 0,
        "staying": 1,
    }
    assert await db.find_one(DeploymentEvent, {"deployment_id": uuid.UUID(alone["id"]), "kind": "migration_skipped"})

    await client.patch(f"/api/v1/nodes/{a['node_id']}", json={"accepting_workloads": True}, headers=provider)
    manual = await _deploy(client, customer, ollama_model, failover_policy="manual")
    await _report(client, a, manual["id"], "READY")
    await enroll_node(provider=provider)
    out = (await client.post(f"/api/v1/nodes/{a['node_id']}/evacuate", headers=provider)).json()
    assert out["staying"] >= 1
    assert (await _dep(db, manual["id"])).migrating_attempt_id is None


async def test_stopping_during_a_move_cleans_up_both_nodes(client, db, make_user, enroll_node, ollama_model):
    provider, a, b, customer, dep = await _serving_on_a(client, make_user, enroll_node, ollama_model)
    await client.post(f"/api/v1/nodes/{a['node_id']}/evacuate", headers=provider)
    await client.post(f"/api/v1/deployments/{dep['id']}/stop", headers=customer)
    stopped = await _dep(db, dep["id"])
    assert stopped.status == "STOPPING" and stopped.migrating_attempt_id is None
    assert (await db.get(Node, uuid.UUID(b["node_id"]))).reserved_ram_mb == 0
    # The undelivered DEPLOY to B was cancelled; A gets the STOP.
    assert await _poll(client, b) == []
    assert [c["type"] for c in await _poll(client, a)] == ["STOP"]


async def test_other_providers_cannot_evacuate_or_report_on_a_move(client, db, make_user, enroll_node, ollama_model):
    provider, a, b, customer, dep = await _serving_on_a(client, make_user, enroll_node, ollama_model)
    _, stranger = await make_user("provider")
    assert (await client.post(f"/api/v1/nodes/{a['node_id']}/evacuate", headers=stranger)).status_code == 404
    await client.post(f"/api/v1/nodes/{a['node_id']}/evacuate", headers=provider)
    intruder = await enroll_node()
    assert (await _report(client, intruder, dep["id"], "READY")).status_code == 404
    # A stale report naming another attempt is refused even from the move's target.
    stale = await _report(client, b, dep["id"], "READY", attempt_id=str(uuid.uuid4()))
    assert stale.status_code == 409
    assert (await _dep(db, dep["id"])).node_id == uuid.UUID(a["node_id"])
