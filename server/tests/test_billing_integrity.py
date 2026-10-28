"""Usage-accounting integrity (security tests 6 and 7, G-22): exactly one estimate per window however often or
concurrently estimates run, unsuccessful requests and interrupted deployments never counted or revived, and
provider-reported token counts treated as claims bounded by what the server observed."""

import asyncio
import uuid
from datetime import timedelta

from app.core.timeutil import utcnow
from app.documents import CostEstimate, Deployment, UsageRecord
from app.services import cost_service
from tests.test_cost_estimates import _ready_deployment, _set_ready_at
from tests.test_gateway import ready_deployment  # noqa: F401  (fixture)


def _usage(dep, node, at, **over) -> UsageRecord:
    fields = {
        "kind": "inference",
        "outcome": "success",
        "deployment_id": uuid.UUID(dep["id"]),
        "node_id": uuid.UUID(node["node_id"]),
        "request_id": uuid.uuid4().hex,
        "input_tokens": 10,
        "output_tokens": 10,
        "response_bytes": 4096,
        "request_bytes": 200,
        "created_at": at,
    }
    return UsageRecord(**(fields | over))


async def test_concurrent_and_repeated_estimate_runs_produce_exactly_one_estimate(
    client, db, enroll_node, make_user, ollama_model
):
    dep, node, *_ = await _ready_deployment(client, db, enroll_node, make_user, ollama_model)
    start = utcnow() - timedelta(hours=1)
    await _set_ready_at(db, dep["id"], start)
    db.add(_usage(dep, node, start + timedelta(minutes=5)))
    await db.commit()
    end = start + timedelta(minutes=30)
    await asyncio.gather(*[cost_service.run_estimates(end) for _ in range(4)], return_exceptions=True)
    await cost_service.run_estimates(end)  # and once more afterwards
    estimates = await db.find(CostEstimate, {"deployment_id": uuid.UUID(dep["id"])})
    periods = [(c.node_id, c.period_start) for c in estimates]
    assert len(periods) == len(set(periods)) and estimates, "a period was counted twice"
    assert sum(c.input_tokens for c in estimates) == 10


async def test_duplicate_metering_of_one_request_is_counted_once(db):
    from pymongo.errors import DuplicateKeyError

    rid = uuid.uuid4().hex
    db.add(UsageRecord(kind="inference", request_id=rid, deployment_id=uuid.uuid4()))
    await db.commit()
    db.add(UsageRecord(kind="inference", request_id=rid, deployment_id=uuid.uuid4()))
    try:
        await db.commit()
        raise AssertionError("duplicate request id was stored")
    except DuplicateKeyError:
        pass


async def test_failed_cancelled_and_timed_out_requests_are_never_counted(
    client, db, enroll_node, make_user, ollama_model
):
    dep, node, *_ = await _ready_deployment(
        client, db, enroll_node, make_user, ollama_model, cpu_core_hour="0", ram_gb_hour="0"
    )
    start = utcnow() - timedelta(hours=1)
    await _set_ready_at(db, dep["id"], start)
    for outcome in ("runtime_error", "cancelled", "timeout", "node_unavailable"):
        db.add(_usage(dep, node, start + timedelta(minutes=2), outcome=outcome, input_tokens=500, output_tokens=500))
    await db.commit()
    await cost_service.run_estimates(start + timedelta(hours=1))
    assert sum(c.input_tokens + c.output_tokens for c in await db.find(CostEstimate)) == 0


async def test_input_token_claims_are_capped_by_the_forwarded_request(client, db, enroll_node, make_user, ollama_model):
    dep, node, *_ = await _ready_deployment(
        client, db, enroll_node, make_user, ollama_model, cpu_core_hour="0", ram_gb_hour="0"
    )
    start = utcnow() - timedelta(hours=1)
    await _set_ready_at(db, dep["id"], start)
    # A runtime claiming a million prompt tokens for a 200-byte request is counted as at most 200 + the template.
    db.add(_usage(dep, node, start + timedelta(minutes=1), input_tokens=1_000_000, output_tokens=0))
    await db.commit()
    await cost_service.run_estimates(start + timedelta(hours=1))
    estimate = await db.find_one(CostEstimate)
    assert estimate.input_tokens == 200 + cost_service.TEMPLATE_TOKENS
    raw = await db.find_one(UsageRecord)
    assert raw.input_tokens == 1_000_000 and raw.token_source is None  # the claim is kept as reported, for audits


async def test_operators_see_providers_whose_claims_exceed_observations(
    client, db, make_user, enroll_node, ollama_model
):
    honest, inflating = await enroll_node(), await enroll_node()
    dep = {"id": str(uuid.uuid4())}
    now = utcnow()
    db.add_all([_usage(dep, honest, now) for _ in range(3)])
    db.add_all([_usage(dep, inflating, now, output_tokens=10**6) for _ in range(3)])
    await db.commit()
    _, operator = await make_user("operator")
    _, customer = await make_user("customer")
    assert (await client.get("/api/v1/admin/anomalies", headers=customer)).status_code == 403
    rows = {r["node_id"]: r for r in (await client.get("/api/v1/admin/anomalies", headers=operator)).json()}
    assert rows[inflating["node_id"]]["flagged"] and rows[inflating["node_id"]]["token_overclaims"] == 3
    assert not rows[honest["node_id"]]["flagged"]


async def test_gateway_records_the_request_size_it_forwarded(client, db, ready_deployment):  # noqa: F811
    dep = ready_deployment["dep"]
    resp = await client.post(
        f"/api/v1/deployments/{dep['id']}/ollama/api/chat",
        json={"messages": [{"role": "user", "content": "x" * 300}]},
        headers=ready_deployment["customer"],
    )
    assert resp.status_code == 200
    record = await db.find_one(UsageRecord, {"kind": "inference"})
    assert record.request_bytes >= 300 and record.response_bytes > 0


async def test_interrupted_deployments_are_never_revived_by_a_worker(client, db, enroll_node, make_user, ollama_model):
    dep, node, *_ = await _ready_deployment(client, db, enroll_node, make_user, ollama_model)
    # The node goes silent: the monitor marks it offline and the deployment unhealthy.
    from app.background.monitors import run_stale_nodes

    await run_stale_nodes(utcnow() + timedelta(hours=1))
    db.expire_all()
    assert (await db.get(Deployment, uuid.UUID(dep["id"]))).status == "UNHEALTHY"
    # It then fails; a late worker report cannot bring it back to READY.
    await db.update_one(Deployment, {"_id": uuid.UUID(dep["id"])}, {"$set": {"status": "FAILED"}})
    await db.commit()
    for state in ("READY", "STARTING"):
        resp = await client.post(
            f"/api/v1/worker/deployments/{dep['id']}/status", json={"state": state}, headers=node["headers"]
        )
        assert resp.status_code in (200, 409)
    db.expire_all()
    assert (await db.get(Deployment, uuid.UUID(dep["id"]))).status == "FAILED"
