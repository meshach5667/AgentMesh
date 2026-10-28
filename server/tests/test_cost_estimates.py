"""Cost estimates: READY time and tokens at the machine's published prices. AgentMesh moves no money: nothing is
deducted, held, split or stopped for lack of funds, and estimates are labelled as estimates."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.timeutil import utcnow
from app.documents import DOCUMENTS, CostEstimate, CreditEntry, Deployment, DeploymentEvent, NodePrice, UsageRecord
from app.services import cost_service
from app.services.cost_service import Interval, ready_intervals
from tests.conftest import give_credit

PRICES = {
    "currency": "NGN",
    "cpu_core_hour": "10",
    "ram_gb_hour": "20",
    "vram_gb_hour": "0",
    "input_tokens_per_million": "1000",
    "output_tokens_per_million": "2000",
}


async def _price_node(client, db, node, **over):
    """The provider publishes prices for its machine; backdated so windows that start in the past are priced."""
    resp = await client.put(
        f"/api/v1/nodes/{node['node_id']}/pricing", json=PRICES | over, headers=node["provider_headers"]
    )
    assert resp.status_code == 200, resp.text
    await db.update_many(
        NodePrice, {"node_id": uuid.UUID(node["node_id"])}, {"$set": {"effective_from": utcnow() - timedelta(days=2)}}
    )
    await db.commit()


async def _ready_deployment(
    client, db, enroll_node, make_user, model, *, provider=None, priced=True, credit="1000000", **price
):
    node = await enroll_node(provider=provider)
    if priced:
        await _price_node(client, db, node, **price)
    customer_user, customer = await make_user("customer")
    if priced and credit:
        await give_credit(db, customer_user, node, credit)
    resp = await client.post("/api/v1/deployments", json={"model_id": str(model.id)}, headers=customer)
    assert resp.status_code == 201, resp.text
    dep = resp.json()
    await client.post(
        f"/api/v1/worker/deployments/{dep['id']}/status", json={"state": "READY"}, headers=node["headers"]
    )
    return dep, node, customer_user, customer


async def _set_ready_at(db, dep_id: str, when):
    """Move the deployment's history so READY began at ``when`` (tests control time)."""
    did = uuid.UUID(dep_id)
    await db.update_many(DeploymentEvent, {"deployment_id": did}, {"$set": {"created_at": when - timedelta(minutes=1)}})
    await db.update_many(DeploymentEvent, {"deployment_id": did, "to_status": "READY"}, {"$set": {"created_at": when}})
    await db.update_one(Deployment, {"_id": did}, {"$set": {"created_at": when - timedelta(minutes=2)}})
    await db.commit()
    db.expire_all()


def test_ready_intervals_follow_lifecycle_events():
    t0 = utcnow()
    n1, n2 = uuid.uuid4(), uuid.uuid4()

    def ev(minutes, to, node):
        return DeploymentEvent.model_construct(
            to_status=to, actor="system", created_at=t0 + timedelta(minutes=minutes), node_id=node
        )

    events = [
        ev(0, "SCHEDULED", n1),
        ev(1, "READY", n1),
        ev(31, "UNHEALTHY", n1),
        ev(40, "SCHEDULED", n2),
        ev(45, "READY", n2),
    ]
    assert ready_intervals(events, t0 + timedelta(minutes=60), None) == [
        Interval(t0 + timedelta(minutes=1), t0 + timedelta(minutes=31), n1),
        Interval(t0 + timedelta(minutes=45), t0 + timedelta(minutes=60), n2),
    ]


async def test_a_free_machine_is_measured_but_nothing_is_owed(client, db, enroll_node, make_user, ollama_model):
    dep, *_ = await _ready_deployment(client, db, enroll_node, make_user, ollama_model, priced=False)
    await _set_ready_at(db, dep["id"], utcnow() - timedelta(hours=2))
    assert await cost_service.run_estimates(utcnow()) == 0
    assert await db.find(CostEstimate) == []


async def test_ready_time_and_tokens_are_estimated_at_the_machine_prices(
    client, db, enroll_node, make_user, ollama_model
):
    provider_user, provider = await make_user("provider")
    dep, node, _, customer = await _ready_deployment(
        client, db, enroll_node, make_user, ollama_model, provider=provider
    )
    start = utcnow() - timedelta(hours=1)
    await _set_ready_at(db, dep["id"], start)
    db.add(
        UsageRecord(
            kind="inference",
            outcome="success",
            deployment_id=uuid.UUID(dep["id"]),
            node_id=uuid.UUID(node["node_id"]),
            request_id=uuid.uuid4().hex,
            input_tokens=500_000,
            output_tokens=250_000,
            created_at=start + timedelta(minutes=5),
        )
    )
    await db.commit()

    now = start + timedelta(hours=1)
    assert await cost_service.run_estimates(now) == 1
    est = await db.find_one(CostEstimate)
    # 1 h x (1 core x 10 + 1 GB x 20) = 30; tokens 0.5M x 1000/M + 0.25M x 2000/M = 1000
    assert est.ready_seconds == pytest.approx(3600, abs=1)
    assert est.resource_amount == pytest.approx(Decimal(30), abs=Decimal("0.01"))
    assert est.token_amount == Decimal(1000) and est.currency == "NGN"
    assert est.rates["cpu_core_hour"] == "10" and est.node_price_id is not None

    # Running again for the same instant adds nothing; a later run only estimates the new time.
    assert await cost_service.run_estimates(now) == 0
    assert await cost_service.run_estimates(now + timedelta(minutes=10)) == 1

    mine = (await client.get("/api/v1/billing/estimates", headers=customer)).json()
    assert len(mine) == 2 and {e["deployment_id"] for e in mine} == {dep["id"]}
    hosted = (await client.get("/api/v1/billing/estimates", headers=provider)).json()
    assert len(hosted) == 2
    # The provider sees a short reference, not who the customer is; the customer quotes the same one when paying.
    reference = (await client.get(f"/api/v1/deployments/{dep['id']}/pricing", headers=customer)).json()
    assert {e["customer_ref"] for e in hosted} == {reference["payment_reference"]} and "customer_id" not in hosted[0]
    _, stranger = await make_user("customer")
    assert (await client.get("/api/v1/billing/estimates", headers=stranger)).json() == []
    summary = (await client.get("/api/v1/billing/estimates/summary", headers=customer)).json()
    assert summary["scope"] == "customer" and summary["totals"][0]["currency"] == "NGN"
    assert Decimal(summary["totals"][0]["amount"]) == sum(Decimal(e["amount"]) for e in mine)

    # No money moved anywhere: the platform has no wallet, ledger, payment or payout collection to write to.
    assert not {"wallets", "transactions", "payments", "payouts", "charges"} & {d.Settings.name for d in DOCUMENTS}


async def test_a_price_cut_mid_window_is_split_and_applies_at_once(client, db, enroll_node, make_user, ollama_model):
    dep, node, *_ = await _ready_deployment(client, db, enroll_node, make_user, ollama_model)
    start = utcnow() - timedelta(hours=2)
    await _set_ready_at(db, dep["id"], start)
    first = await db.find_one(NodePrice, {"node_id": uuid.UUID(node["node_id"])})
    db.add(
        NodePrice(
            node_id=first.node_id,
            provider_id=first.provider_id,
            version=2,
            currency="NGN",
            effective_from=start + timedelta(hours=1),
            cpu_core_hour=Decimal(0),
            ram_gb_hour=Decimal(0),
        )
    )
    await db.commit()
    assert await cost_service.run_estimates(start + timedelta(hours=2)) == 1  # the second hour is free
    est = await db.find_one(CostEstimate)
    assert est.period_end == start + timedelta(hours=1)
    assert est.resource_amount == pytest.approx(Decimal(30), abs=Decimal("0.01"))


async def test_unhealthy_time_is_not_counted(client, db, enroll_node, make_user, ollama_model):
    dep, *_ = await _ready_deployment(client, db, enroll_node, make_user, ollama_model)
    start = utcnow() - timedelta(hours=1)
    await _set_ready_at(db, dep["id"], start)
    db.add(
        DeploymentEvent(
            deployment_id=uuid.UUID(dep["id"]),
            from_status="READY",
            to_status="UNHEALTHY",
            actor="system",
            created_at=start + timedelta(minutes=15),
        )
    )
    await db.commit()
    await cost_service.run_estimates(start + timedelta(hours=1))
    est = await db.find_one(CostEstimate)
    assert est.ready_seconds == pytest.approx(900, abs=1)


async def test_priced_service_needs_verified_credit_which_usage_draws_down(
    client, db, enroll_node, make_user, ollama_model
):
    """No credit with the provider: no placement on its priced machine. With credit: placed; each estimate draws the
    credit down once; when it is used up the deployment pauses and the gateway refuses requests."""
    node = await enroll_node()
    await _price_node(client, db, node)  # 30 NGN/h for this reservation
    customer_user, customer = await make_user("customer")
    refused = await client.post("/api/v1/deployments", json={"model_id": str(ollama_model.id)}, headers=customer)
    assert refused.status_code == 503 and refused.json()["detail"]["reasons"] == {"no_prepaid_credit": 1}
    await give_credit(db, customer_user, node, "20")  # less than one hour (30)
    still = await client.post("/api/v1/deployments", json={"model_id": str(ollama_model.id)}, headers=customer)
    assert still.status_code == 503
    await give_credit(db, customer_user, node, "25")  # 45 in total: enough for an hour
    dep = (await client.post("/api/v1/deployments", json={"model_id": str(ollama_model.id)}, headers=customer)).json()
    await client.post(
        f"/api/v1/worker/deployments/{dep['id']}/status", json={"state": "READY"}, headers=node["headers"]
    )
    start = utcnow() - timedelta(hours=2)
    await _set_ready_at(db, dep["id"], start)

    await cost_service.run_estimates(start + timedelta(hours=1))  # 30 used: 15 left, keeps serving
    db.expire_all()
    assert (await db.get(Deployment, uuid.UUID(dep["id"]))).status == "READY"
    await cost_service.run_estimates(start + timedelta(hours=1))  # same instant again: nothing drawn twice
    credits = (await client.get("/api/v1/credits", headers=customer)).json()
    assert Decimal(credits["balances"][0]["balance"]) == Decimal(15)

    await cost_service.run_estimates(start + timedelta(hours=2))  # another 30: used up
    db.expire_all()
    paused = await db.get(Deployment, uuid.UUID(dep["id"]))
    assert paused.status == "NEEDS_ATTENTION" and paused.error_code == "CREDIT_EXHAUSTED" and paused.node_id is None
    entries = await db.find(CreditEntry, {"kind": "usage"})
    assert len(entries) == 2 and len({e.key for e in entries}) == 2


async def test_the_gateway_refuses_requests_once_credit_is_used_up(client, db, enroll_node, make_user, ollama_model):
    dep, node, customer_user, customer = await _ready_deployment(client, db, enroll_node, make_user, ollama_model)
    from bson import Decimal128

    from app.documents import CreditBalance

    await db.update_many(CreditBalance, {}, {"$set": {"balance": Decimal128("0")}})
    await db.commit()
    resp = await client.post(
        f"/api/v1/deployments/{dep['id']}/ollama/api/chat", json={"messages": []}, headers=customer
    )
    assert resp.status_code == 402 and resp.json()["error"]["code"] == "credit_exhausted"


async def test_estimated_output_tokens_are_bounded_by_measured_bytes(client, db, enroll_node, make_user, ollama_model):
    dep, node, *_ = await _ready_deployment(
        client, db, enroll_node, make_user, ollama_model, cpu_core_hour="0", ram_gb_hour="0"
    )
    start = utcnow() - timedelta(hours=1)
    await _set_ready_at(db, dep["id"], start)
    db.add(
        UsageRecord(
            kind="inference",
            outcome="success",
            deployment_id=uuid.UUID(dep["id"]),
            node_id=uuid.UUID(node["node_id"]),
            request_id=uuid.uuid4().hex,
            input_tokens=0,
            output_tokens=1_000_000,
            response_bytes=2048,
            created_at=start + timedelta(minutes=1),
        )
    )
    await db.commit()
    await cost_service.run_estimates(start + timedelta(hours=1))
    est = await db.find_one(CostEstimate)
    assert est.output_tokens == 2048
