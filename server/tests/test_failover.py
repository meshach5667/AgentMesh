"""Automatic failover and safe rerouting, end to end through the worker API, the scheduler and the background
monitors (with controlled time). Each test names the scenario it proves."""

import asyncio
import uuid
from datetime import timedelta
from decimal import Decimal

from app.background import monitors
from app.core.config import settings
from app.core.timeutil import utcnow
from app.documents import (
    AuditLog,
    CostEstimate,
    Deployment,
    DeploymentAttempt,
    DeploymentEvent,
    Node,
    NodeCommand,
    ResourceReservation,
)
from app.services import cost_service
from tests.conftest import HARDWARE

GPU_HARDWARE = HARDWARE | {"gpus": [{"vendor": "nvidia", "model": "Test GPU", "vram_mb": 16384}]}


async def _deploy(client, headers, model, **body):
    resp = await client.post("/api/v1/deployments", json={"model_id": str(model.id), **body}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _report(client, node, dep_id, state, **extra):
    return await client.post(
        f"/api/v1/worker/deployments/{dep_id}/status", json={"state": state, **extra}, headers=node["headers"]
    )


async def _heartbeat(client, node, **extra):
    return await client.post(
        "/api/v1/worker/heartbeat", json={"worker_version": "t", "deployments": []} | extra, headers=node["headers"]
    )


async def _dep(db, dep_id) -> Deployment:
    db.expire_all()
    return await db.get(Deployment, uuid.UUID(str(dep_id)))


async def _attempts(db, dep_id) -> list[DeploymentAttempt]:
    return await db.find(DeploymentAttempt, {"deployment_id": uuid.UUID(str(dep_id))}, sort=[("number", 1)])


async def _set_price(client, node, cpu, currency="NGN"):
    body = {
        "currency": currency,
        "cpu_core_hour": cpu,
        "ram_gb_hour": "0",
        "vram_gb_hour": "0",
        "input_tokens_per_million": "0",
        "output_tokens_per_million": "0",
    }
    resp = await client.put(f"/api/v1/nodes/{node['node_id']}/pricing", json=body, headers=node["provider_headers"])
    assert resp.status_code == 200, resp.text


async def _age_heartbeat(db, node, seconds):
    await db.update_one(
        Node, {"_id": uuid.UUID(node["node_id"])}, {"$set": {"last_heartbeat": utcnow() - timedelta(seconds=seconds)}}
    )
    await db.commit()


# 1 -----------------------------------------------------------------------------------------------------------


async def test_1_a_healthy_node_receives_a_compatible_workload_as_attempt_1(
    client, db, enroll_node, make_user, ollama_model
):
    node = await enroll_node()
    shown = (await client.get(f"/api/v1/nodes/{node['node_id']}", headers=node["provider_headers"])).json()
    assert shown["health"] == "ACTIVE" and shown["schedulable"] is True
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    assert dep["node_id"] == node["node_id"] and dep["status"] == "SCHEDULED"
    (attempt,) = await _attempts(db, dep["id"])
    assert attempt.number == 1 and attempt.active and str(attempt.id) == dep["attempt_id"]
    cmd = await db.find_one(NodeCommand, {"type": "DEPLOY"})
    assert cmd.payload["attempt_id"] == dep["attempt_id"]  # the worker learns which attempt it runs
    shown = (await client.get(f"/api/v1/nodes/{node['node_id']}", headers=node["provider_headers"])).json()
    assert shown["health"] == "BUSY"


# 2, 15 ------------------------------------------------------------------------------------------------------


async def test_2_a_late_heartbeat_stops_new_work_and_only_the_timeout_moves_work(
    client, db, enroll_node, make_user, ollama_model
):
    _, provider = await make_user("provider")
    a = await enroll_node(provider=provider, ram_mb=8192)
    b = await enroll_node(provider=provider, ram_mb=4096)
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    assert dep["node_id"] == a["node_id"]

    # One missed interval: DEGRADED (no new work), nothing is moved, and the event is recorded once.
    await _age_heartbeat(db, a, settings.HEARTBEAT_DEGRADED_SECONDS + 5)
    assert await monitors.run_stale_nodes() == 0
    assert await monitors.run_stale_nodes() == 0
    assert await db.count(AuditLog, {"action": "node.heartbeat_late", "resource_id": a["node_id"]}) == 1
    shown = (await client.get(f"/api/v1/nodes/{a['node_id']}", headers=provider)).json()
    assert shown["health"] == "DEGRADED" and shown["schedulable"] is False
    assert (await _dep(db, dep["id"])).node_id == uuid.UUID(a["node_id"])
    second = await _deploy(client, customer, ollama_model)
    assert second["node_id"] == b["node_id"]  # the late node gets no new work

    # Several missed intervals: OFFLINE, and its provisioning work moves to the healthy node.
    await _age_heartbeat(db, a, settings.HEARTBEAT_TIMEOUT_SECONDS + 5)
    assert await monitors.run_stale_nodes() == 1
    moved = await _dep(db, dep["id"])
    assert moved.status == "SCHEDULED" and moved.node_id == uuid.UUID(b["node_id"])
    assert await db.count(AuditLog, {"action": "node.offline", "resource_id": a["node_id"]}) == 1


async def test_15_a_delayed_heartbeat_cannot_overwrite_newer_state(client, db, enroll_node):
    node = await enroll_node()
    fresh = await _heartbeat(client, node, boot_id="boot-aaaa", seq=5, metrics={"cpu_percent": 50.0})
    assert fresh.json()["stale"] is False
    late = await _heartbeat(client, node, boot_id="boot-aaaa", seq=3, metrics={"cpu_percent": 99.0}, available=False)
    assert late.status_code == 200 and late.json()["stale"] is True
    db.expire_all()
    row = await db.get(Node, uuid.UUID(node["node_id"]))
    assert row.last_metrics == {"cpu_percent": 50.0} and row.worker_available is True and row.heartbeat_seq == 5
    # A restarted worker (new boot id) starts its sequence again and is accepted.
    assert (await _heartbeat(client, node, boot_id="boot-bbbb", seq=1)).json()["stale"] is False


# 3, 4, 5, 6 -------------------------------------------------------------------------------------------------


async def test_3_to_6_a_failed_node_is_replaced_and_the_history_records_it(
    client, db, enroll_node, make_user, ollama_model
):
    _, provider = await make_user("provider")
    a = await enroll_node(provider=provider, ram_mb=8192)
    b = await enroll_node(provider=provider, ram_mb=4096)
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    await _report(client, a, dep["id"], "READY")

    # The node disappears while serving: UNHEALTHY at once, moved after the grace period.
    await _age_heartbeat(db, a, settings.HEARTBEAT_TIMEOUT_SECONDS + 5)
    await monitors.run_stale_nodes()
    assert (await _dep(db, dep["id"])).status == "UNHEALTHY"
    later = utcnow() + timedelta(seconds=settings.UNHEALTHY_GRACE_SECONDS + 1)
    await monitors.run_deployment_timeouts(now=later)
    moved = await _dep(db, dep["id"])
    assert moved.status == "SCHEDULED" and moved.node_id == uuid.UUID(b["node_id"])

    # The replacement runs it.
    assert (await _report(client, b, dep["id"], "READY")).status_code == 200
    assert (await _dep(db, dep["id"])).status == "READY"

    first, second = await _attempts(db, dep["id"])
    assert (first.number, first.active, first.outcome, first.error_code) == (
        1,
        False,
        "node_failed",
        "UNHEALTHY_TIMEOUT",
    )
    assert (second.number, second.active, second.state, second.node_id) == (2, True, "running", uuid.UUID(b["node_id"]))
    kinds = [e.kind for e in await db.find(DeploymentEvent, {"deployment_id": moved.id}, sort=[("created_at", 1)])]
    assert kinds.index("attempt_failed") < kinds.index("rerouted")
    listed = (await client.get(f"/api/v1/deployments/{dep['id']}/attempts", headers=customer)).json()
    assert [r["outcome"] for r in listed] == ["node_failed", None] and listed[1]["state"] == "running"
    assert listed[0]["provider"].startswith("Provider ")


# 7 ----------------------------------------------------------------------------------------------------------


async def test_7_concurrent_schedulers_never_assign_a_workload_twice(client, db, enroll_node, make_user, ollama_model):
    a = await enroll_node()
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    await _report(client, a, dep["id"], "FAILED", error_code="INSUFFICIENT_MEMORY", message="oom")
    assert (await _dep(db, dep["id"])).status == "PENDING"
    await enroll_node()
    await enroll_node()
    await db.update_one(Deployment, {"_id": uuid.UUID(dep["id"])}, {"$set": {"next_placement_at": utcnow()}})
    await db.commit()

    results = await asyncio.gather(*[monitors.run_pending_placements() for _ in range(5)], return_exceptions=True)
    assert sum(r for r in results if isinstance(r, int)) == 1
    did = uuid.UUID(dep["id"])
    assert await db.count(DeploymentAttempt, {"deployment_id": did, "active": True}) == 1
    assert await db.count(ResourceReservation, {"deployment_id": did, "status": "ACTIVE"}) == 1
    placed = await _dep(db, dep["id"])
    assert await db.count(NodeCommand, {"deployment_id": did, "type": "DEPLOY", "node_id": placed.node_id}) == 1


# 8 ----------------------------------------------------------------------------------------------------------


async def test_8_a_failed_dispatch_moves_the_workload_to_the_next_candidate(
    client, db, enroll_node, make_user, ollama_model
):
    _, provider = await make_user("provider")
    a = await enroll_node(provider=provider, ram_mb=8192)
    b = await enroll_node(provider=provider, ram_mb=4096)
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    cmd = await db.find_one(NodeCommand, {"node_id": uuid.UUID(a["node_id"]), "type": "DEPLOY"})
    cmd.status, cmd.attempts, cmd.lease_expires_at = "LEASED", cmd.max_attempts, utcnow() - timedelta(seconds=1)
    await db.commit()
    assert await monitors.run_command_leases() == 1
    moved = await _dep(db, dep["id"])
    assert moved.status == "SCHEDULED" and moved.node_id == uuid.UUID(b["node_id"])
    assert (await _attempts(db, dep["id"]))[0].error_code == "NODE_UNRESPONSIVE"


# 9, 18 ------------------------------------------------------------------------------------------------------


async def test_9_and_18_with_no_replacement_it_waits_and_is_placed_later_even_after_a_restart(
    client, db, enroll_node, make_user, ollama_model
):
    a = await enroll_node()
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    await _report(client, a, dep["id"], "FAILED", error_code="RUNTIME_START_FAILED", message="crashed")
    waiting = await _dep(db, dep["id"])
    assert waiting.status == "PENDING" and waiting.node_id is None and waiting.pending_since is not None
    delay = (waiting.next_placement_at - utcnow()).total_seconds()
    assert 0.7 * settings.PLACEMENT_RETRY_BASE_SECONDS <= delay <= 1.3 * settings.PLACEMENT_RETRY_BASE_SECONDS
    got = (await client.get(f"/api/v1/deployments/{dep['id']}", headers=customer)).json()
    assert got["status"] == "PENDING" and got["next_placement_at"] is not None

    # Still nothing: the next retry backs off further (state is persisted, so any process picks it up).
    future = utcnow() + timedelta(seconds=settings.PLACEMENT_RETRY_BASE_SECONDS * 2)
    assert await monitors.run_pending_placements(now=future) == 0
    again = await _dep(db, dep["id"])
    assert again.placement_retries == 1 and again.next_placement_at > waiting.next_placement_at

    # A node appears; the next pass (in a fresh session, as after a service restart) places it.
    b = await enroll_node()
    assert await monitors.run_pending_placements(now=utcnow() + timedelta(hours=1)) == 1
    placed = await _dep(db, dep["id"])
    assert placed.status == "SCHEDULED" and placed.node_id == uuid.UUID(b["node_id"]) and placed.pending_since is None


# 10 ---------------------------------------------------------------------------------------------------------


async def test_10_a_gpu_workload_never_lands_on_a_cpu_only_node(client, db, enroll_node, make_user, ollama_model):
    cpu_only = await enroll_node()
    _, customer = await make_user("customer")
    refused = await client.post(
        "/api/v1/deployments",
        json={"model_id": str(ollama_model.id), "config": {"require_gpu": True}},
        headers=customer,
    )
    assert refused.status_code == 503 and refused.json()["detail"]["reasons"] == {"incompatible_hardware": 1}

    gpu = await enroll_node(hardware=GPU_HARDWARE, vram_mb=16384)
    dep = await _deploy(client, customer, ollama_model, config={"require_gpu": True})
    assert dep["node_id"] == gpu["node_id"]
    await _report(client, gpu, dep["id"], "FAILED", error_code="INSUFFICIENT_MEMORY", message="oom")
    after = await _dep(db, dep["id"])
    assert after.status == "PENDING" and after.node_id is None  # the CPU-only node is not a replacement
    assert cpu_only["node_id"] not in str(await _attempts(db, dep["id"]))


# 11 ---------------------------------------------------------------------------------------------------------


async def test_11_a_dearer_replacement_needs_the_customers_approval(client, db, enroll_node, make_user, ollama_model):
    cheap = await enroll_node()
    await _set_price(client, cheap, "5")
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    dear = await enroll_node()
    await _set_price(client, dear, "50")
    await _report(client, cheap, dep["id"], "FAILED", error_code="INSUFFICIENT_MEMORY", message="oom")
    paused = await _dep(db, dep["id"])
    assert paused.status == "NEEDS_ATTENTION" and paused.error_code == "PRICE_APPROVAL_REQUIRED"
    assert await db.count(DeploymentAttempt, {"deployment_id": paused.id}) == 1  # not moved silently

    # Retrying without raising the limit changes nothing; approving a higher price moves it.
    retried = (await client.post(f"/api/v1/deployments/{dep['id']}/retry", headers=customer)).json()
    assert retried["status"] == "NEEDS_ATTENTION"
    patched = await client.patch(f"/api/v1/deployments/{dep['id']}", json={"max_hourly_price": "60"}, headers=customer)
    assert patched.status_code == 200 and Decimal(patched.json()["max_hourly_price"]) == 60
    placed = (await client.post(f"/api/v1/deployments/{dep['id']}/retry", headers=customer)).json()
    assert placed["status"] == "SCHEDULED" and placed["node_id"] == dear["node_id"]


async def test_11b_an_explicit_limit_is_never_exceeded_by_recovery(client, db, enroll_node, make_user, ollama_model):
    cheap = await enroll_node()
    await _set_price(client, cheap, "5")
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model, max_hourly_price="10")
    dear = await enroll_node()
    await _set_price(client, dear, "50")
    await _report(client, cheap, dep["id"], "FAILED", error_code="INSUFFICIENT_MEMORY", message="oom")
    assert (await _dep(db, dep["id"])).status == "PENDING"  # waits for a machine within the limit
    assert await monitors.run_pending_placements(now=utcnow() + timedelta(hours=1)) == 0
    assert (await _dep(db, dep["id"])).node_id is None


# 12 ---------------------------------------------------------------------------------------------------------


async def test_12_a_deployment_marked_not_safe_to_move_is_never_moved_automatically(
    client, db, enroll_node, make_user, ollama_model
):
    _, provider = await make_user("provider")
    a = await enroll_node(provider=provider, ram_mb=8192)
    b = await enroll_node(provider=provider, ram_mb=4096)
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model, failover_policy="manual")
    await _report(client, a, dep["id"], "FAILED", error_code="INSUFFICIENT_MEMORY", message="oom")
    held = await _dep(db, dep["id"])
    assert held.status == "NEEDS_ATTENTION" and held.node_id is None
    assert await db.count(NodeCommand, {"node_id": uuid.UUID(b["node_id"])}) == 0
    resumed = (await client.post(f"/api/v1/deployments/{dep['id']}/retry", headers=customer)).json()
    assert resumed["status"] == "SCHEDULED" and resumed["node_id"] == b["node_id"]


async def test_12b_a_failure_caused_by_the_model_is_not_retried_elsewhere(
    client, db, enroll_node, make_user, ollama_model
):
    a = await enroll_node()
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    await enroll_node()  # a replacement exists, yet another node would fail the same way
    resp = await _report(client, a, dep["id"], "FAILED", error_code="MODEL_NOT_FOUND", message="no such model")
    assert resp.status_code == 200
    failed = await _dep(db, dep["id"])
    assert failed.status == "FAILED" and failed.error_code == "MODEL_NOT_FOUND"
    assert await db.count(DeploymentAttempt, {"deployment_id": failed.id}) == 1


# 13 ---------------------------------------------------------------------------------------------------------


async def test_13_a_recovered_node_cannot_reclaim_a_superseded_workload(
    client, db, enroll_node, make_user, ollama_model
):
    _, provider = await make_user("provider")
    a = await enroll_node(provider=provider, ram_mb=8192)
    b = await enroll_node(provider=provider, ram_mb=4096)
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    old_attempt = dep["attempt_id"]
    await _report(client, a, dep["id"], "FAILED", error_code="INSUFFICIENT_MEMORY", message="oom")
    moved = await _dep(db, dep["id"])
    assert moved.node_id == uuid.UUID(b["node_id"])

    # The old node comes back and claims it is running the workload: refused and told to stop.
    assert (await _report(client, a, dep["id"], "READY")).status_code == 404
    hb = await _heartbeat(client, a, deployments=[{"deployment_id": dep["id"], "state": "running", "healthy": True}])
    assert hb.json()["stop_deployments"] == [dep["id"]]
    # A report naming the superseded attempt is refused even from the current node.
    stale = await _report(client, b, dep["id"], "READY", attempt_id=old_attempt)
    assert stale.status_code == 409
    assert (await _dep(db, dep["id"])).status == "SCHEDULED"
    current = await _report(client, b, dep["id"], "READY", attempt_id=str(moved.attempt_id))
    assert current.status_code == 200


# 14 ---------------------------------------------------------------------------------------------------------


async def test_14_retry_limits_end_in_a_clear_failure(client, db, enroll_node, make_user, ollama_model, monkeypatch):
    monkeypatch.setattr(settings, "MAX_SCHEDULE_ATTEMPTS", 2)
    _, provider = await make_user("provider")
    a = await enroll_node(provider=provider, ram_mb=8192)
    b = await enroll_node(provider=provider, ram_mb=4096)
    await enroll_node(provider=provider, ram_mb=2048)
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    await _report(client, a, dep["id"], "FAILED", error_code="INSUFFICIENT_MEMORY", message="oom")
    await _report(client, b, dep["id"], "FAILED", error_code="INSUFFICIENT_MEMORY", message="oom")
    final = await _dep(db, dep["id"])
    assert final.status == "FAILED" and "retry limit" in final.error_message
    assert await db.find_one(DeploymentEvent, {"deployment_id": final.id, "kind": "retry_limit"}) is not None


async def test_14b_waiting_too_long_ends_in_a_clear_failure(client, db, enroll_node, make_user, ollama_model):
    only = await enroll_node()
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    await _report(client, only, dep["id"], "FAILED", error_code="INSUFFICIENT_MEMORY", message="oom")
    assert (await _dep(db, dep["id"])).status == "PENDING"
    await db.update_one(
        Deployment,
        {"_id": uuid.UUID(dep["id"])},
        {"$set": {"pending_since": utcnow() - timedelta(seconds=settings.PLACEMENT_PENDING_MAX_SECONDS + 1)}},
    )
    await db.commit()
    await monitors.run_pending_placements(now=utcnow() + timedelta(hours=2))
    gave_up = await _dep(db, dep["id"])
    assert gave_up.status == "FAILED" and gave_up.error_code == "NO_ELIGIBLE_NODE"


# 16 ---------------------------------------------------------------------------------------------------------


async def test_16_a_provider_cannot_claim_or_change_another_providers_assignment(
    client, db, enroll_node, make_user, ollama_model
):
    victim = await enroll_node()
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model)
    intruder = await enroll_node()  # another provider's machine
    assert dep["node_id"] == victim["node_id"]
    for state in ("READY", "FAILED", "STOPPED"):
        assert (await _report(client, intruder, dep["id"], state)).status_code == 404
    cmd = await db.find_one(NodeCommand, {"deployment_id": uuid.UUID(dep["id"])})
    ack = await client.post(
        f"/api/v1/worker/commands/{cmd.id}/ack", json={"status": "failed", "error": "x"}, headers=intruder["headers"]
    )
    assert ack.status_code == 404
    kept = await _dep(db, dep["id"])
    assert kept.node_id == uuid.UUID(victim["node_id"]) and kept.status == "SCHEDULED"


# 17 ---------------------------------------------------------------------------------------------------------


async def test_17_repeated_failures_never_duplicate_results_or_cost_estimates(
    client, db, enroll_node, make_user, ollama_model
):
    _, provider = await make_user("provider")
    nodes = [await enroll_node(provider=provider, ram_mb=ram) for ram in (8192, 6144, 4096)]
    for n in nodes:
        await _set_price(client, n, "10")
    _, customer = await make_user("customer")
    dep = await _deploy(client, customer, ollama_model, max_hourly_price="100")
    start = utcnow() - timedelta(hours=1)
    for i, n in enumerate(nodes[:2]):
        await _report(client, n, dep["id"], "READY")
        await _report(client, n, dep["id"], "READY")  # a duplicated report changes nothing
        if i == 0:
            await _report(client, n, dep["id"], "STOPPED", error_code="WORKLOAD_EXITED", message="exited")
    events = await db.find(DeploymentEvent, {"deployment_id": uuid.UUID(dep["id"]), "to_status": "READY"})
    assert len(events) == 2  # one READY per attempt, not per report
    await db.update_many(DeploymentEvent, {"deployment_id": uuid.UUID(dep["id"])}, {"$set": {"created_at": start}})
    await db.commit()
    await asyncio.gather(*[cost_service.run_estimates() for _ in range(4)], return_exceptions=True)
    estimates = await db.find(CostEstimate, {"deployment_id": uuid.UUID(dep["id"])})
    keys = [(e.node_id, e.period_start) for e in estimates]
    assert len(keys) == len(set(keys))


# Node-level failure handling ---------------------------------------------------------------------------------


async def test_repeated_failures_take_a_node_out_of_scheduling_for_a_cooldown(
    client, db, enroll_node, make_user, ollama_model, monkeypatch
):
    monkeypatch.setattr(settings, "NODE_FAILURE_THRESHOLD", 2)
    flaky = await enroll_node(ram_mb=8192)
    _, customer = await make_user("customer")
    for _ in range(2):
        dep = await _deploy(client, customer, ollama_model)
        assert dep["node_id"] == flaky["node_id"]
        await _report(client, flaky, dep["id"], "FAILED", error_code="RUNTIME_START_FAILED", message="crash")
    shown = (await client.get(f"/api/v1/nodes/{flaky['node_id']}", headers=flaky["provider_headers"])).json()
    assert shown["health"] == "DEGRADED" and shown["degraded_until"] is not None
    assert await db.find_one(AuditLog, {"action": "node.degraded", "resource_id": flaky["node_id"]}) is not None
    refused = await client.post("/api/v1/deployments", json={"model_id": str(ollama_model.id)}, headers=customer)
    assert refused.status_code == 503 and refused.json()["detail"]["reasons"] == {"node_degraded": 1}
    events = (await client.get(f"/api/v1/nodes/{flaky['node_id']}/events", headers=flaky["provider_headers"])).json()
    assert any(e["action"] == "node.degraded" for e in events)
