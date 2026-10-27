"""Per-machine prices: providers set them, placement picks the cheapest machine within the customer's limits, and
billing never charges more than the rates a deployment was placed at."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.timeutil import utcnow
from app.documents import AuditLog, Charge, NodePrice, PricingRule, UsageRecord
from app.services import billing_service, reconciliation_service
from tests.test_billing import _set_ready_at, _wallet

# The ollama_model deployment reserves 1 CPU core and 1 GB of RAM.
NETWORK = {
    "cpu_core_hour": "10",
    "ram_gb_hour": "20",
    "vram_gb_hour": "0",
    "input_tokens_per_million": "1000",
    "output_tokens_per_million": "2000",
}


def prices(cpu="10", ram="20", vram="0", tin="1000", tout="2000") -> dict:
    return {
        "cpu_core_hour": cpu,
        "ram_gb_hour": ram,
        "vram_gb_hour": vram,
        "input_tokens_per_million": tin,
        "output_tokens_per_million": tout,
    }


async def _network(db):
    db.add(
        PricingRule(
            id=uuid.uuid4(),
            version=1,
            currency="NGN",
            effective_from=utcnow() - timedelta(days=1),
            platform_fee_rate=Decimal("0.1"),
            **{k: Decimal(v) for k, v in NETWORK.items()},
        )
    )
    await db.commit()


async def _set_price(client, node, **over):
    resp = await client.put(
        f"/api/v1/nodes/{node['node_id']}/pricing", json=prices(**over), headers=node["provider_headers"]
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _customer(client, make_user, credit="5000"):
    user, headers = await make_user("customer")
    if credit:
        await client.post("/api/v1/wallets/deposit", json={"amount": credit}, headers=headers)
    return user, headers


async def _deploy(client, headers, model, **body):
    return await client.post("/api/v1/deployments", json={"model_id": str(model.id), **body}, headers=headers)


async def test_providers_price_their_own_machines_only(client, db, enroll_node, make_user):
    node = await enroll_node()
    view = await client.get(f"/api/v1/nodes/{node['node_id']}/pricing", headers=node["provider_headers"])
    assert view.status_code == 200 and view.json()["charging"] is None and view.json()["history"] == []

    out = await _set_price(client, node, cpu="7.5")
    assert out["charging"]["source"] == "node" and Decimal(out["charging"]["cpu_core_hour"]) == Decimal("7.5")
    assert [h["version"] for h in out["history"]] == [1]
    out = await _set_price(client, node, cpu="6")
    assert [h["version"] for h in out["history"]] == [2, 1]
    assert await db.find_one(AuditLog, {"action": "node.price_set"}) is not None

    _, other_provider = await make_user("provider")
    _, customer = await make_user("customer")
    url = f"/api/v1/nodes/{node['node_id']}/pricing"
    assert (await client.put(url, json=prices(), headers=other_provider)).status_code == 404
    assert (await client.put(url, json=prices(), headers=customer)).status_code == 403
    assert (await client.get(url, headers=customer)).status_code == 404
    _, operator = await make_user("operator")
    assert (await client.get(url, headers=operator)).status_code == 200


@pytest.mark.parametrize("bad", [{"cpu_core_hour": "-1"}, {"ram_gb_hour": "2000000"}, {"surprise": "1"}])
async def test_invalid_prices_are_refused(client, enroll_node, bad):
    node = await enroll_node()
    resp = await client.put(
        f"/api/v1/nodes/{node['node_id']}/pricing", json=prices() | bad, headers=node["provider_headers"]
    )
    assert resp.status_code == 422


async def test_placement_picks_the_cheapest_machine(client, db, enroll_node, make_user, ollama_model):
    await _network(db)
    dear, cheap, middle = await enroll_node(), await enroll_node(), await enroll_node()
    await _set_price(client, dear, cpu="9")
    await _set_price(client, cheap, cpu="3")
    await _set_price(client, middle, cpu="5")
    _, customer = await _customer(client, make_user)

    quote = await client.post("/api/v1/deployments/quote", json={"model_id": str(ollama_model.id)}, headers=customer)
    assert quote.status_code == 200, quote.text
    q = quote.json()["by_runtime"][0]
    assert q["eligible_nodes"] == 3 and Decimal(q["hourly"]) == Decimal(3 + 20)
    assert Decimal(q["max_hourly_price"]) == Decimal(30)  # the network price of this reservation

    first = (await _deploy(client, customer, ollama_model)).json()
    second = (await _deploy(client, customer, ollama_model)).json()
    assert first["node_id"] == cheap["node_id"]
    # The cheap machine still has room (4 cores), so it is chosen again.
    assert second["node_id"] == cheap["node_id"]
    pricing = (await client.get(f"/api/v1/deployments/{first['id']}/pricing", headers=customer)).json()
    assert Decimal(pricing["hourly"]) == Decimal(23) and pricing["rates"]["source"] == "node"


async def test_machines_above_the_network_prices_need_a_higher_limit(client, db, enroll_node, make_user, ollama_model):
    await _network(db)
    node = await enroll_node()
    await _set_price(client, node, cpu="50")
    _, customer = await _customer(client, make_user)

    refused = await _deploy(client, customer, ollama_model)
    assert refused.status_code == 503
    assert refused.json()["detail"]["reasons"] == {"over_price_limit": 1}
    assert "price limit" in refused.json()["detail"]["message"]

    raised = await _deploy(client, customer, ollama_model, max_hourly_price="100")
    assert raised.status_code == 201, raised.text
    assert raised.json()["node_id"] == node["node_id"] and Decimal(raised.json()["max_hourly_price"]) == 100

    pricey_tokens = await enroll_node()
    await _set_price(client, pricey_tokens, cpu="0", ram="0", tout="9000")  # free per hour, dear per token
    q = (
        await client.post(
            "/api/v1/deployments/quote",
            json={"model_id": str(ollama_model.id), "max_token_price": "2000"},
            headers=customer,
        )
    ).json()["by_runtime"][0]
    # Over the default hourly limit (70 > 30), and over the token limit (9000 > 2000).
    assert q["over_price_limit"] == 2 and q["eligible_nodes"] == 0


async def test_prepaid_check_uses_the_machine_price(client, db, enroll_node, make_user, ollama_model):
    node = await enroll_node()
    await _set_price(client, node, cpu="100", ram="0")  # no network prices: no default limit
    _, customer = await _customer(client, make_user, credit="50")
    resp = await _deploy(client, customer, ollama_model)
    assert resp.status_code == 402
    assert resp.json()["detail"]["code"] == "insufficient_balance"


async def test_billing_uses_machine_prices_and_never_exceeds_the_placement_rates(
    client, db, enroll_node, make_user, ollama_model
):
    await _network(db)
    provider_user, provider = await make_user("provider")
    node = await enroll_node(provider=provider)
    await _set_price(client, node, cpu="4", ram="8", tin="500", tout="500")
    customer_user, customer = await _customer(client, make_user)
    dep = (await _deploy(client, customer, ollama_model)).json()
    await client.post(
        f"/api/v1/worker/deployments/{dep['id']}/status", json={"state": "READY"}, headers=node["headers"]
    )
    start = utcnow() - timedelta(hours=3)
    await _set_ready_at(db, dep["id"], start)
    db.add(
        UsageRecord(
            kind="inference",
            outcome="success",
            deployment_id=uuid.UUID(dep["id"]),
            node_id=uuid.UUID(node["node_id"]),
            request_id=uuid.uuid4().hex,
            input_tokens=1_000,
            output_tokens=1_000,
            response_bytes=10_000,
            request_bytes=10_000,
            created_at=start + timedelta(minutes=5),
        )
    )
    await db.commit()

    # The provider raises prices after an hour (only new placements pay that), then cuts them after two.
    raise_at, cut_at = start + timedelta(hours=1), start + timedelta(hours=2)
    rows = await db.find(NodePrice, {"node_id": uuid.UUID(node["node_id"])})
    assert len(rows) == 1
    await db.update_one(NodePrice, {"_id": rows[0].id}, {"$set": {"effective_from": start - timedelta(days=1)}})
    for version, when, cpu in ((2, raise_at, "40"), (3, cut_at, "1")):
        db.add(
            NodePrice(
                id=uuid.uuid4(),
                node_id=uuid.UUID(node["node_id"]),
                provider_id=rows[0].provider_id,
                version=version,
                currency="NGN",
                effective_from=when,
                cpu_core_hour=Decimal(cpu),
                ram_gb_hour=Decimal("8"),
                input_tokens_per_million=Decimal("500"),
                output_tokens_per_million=Decimal("500"),
            )
        )
    await db.commit()

    assert await billing_service.run_billing(start + timedelta(hours=3)) == 3
    charges = await db.find(Charge, sort=[("period_start", 1)])
    # Hour 1 at the placement rates (4 + 8) plus 2000 tokens at 500/M; hour 2 still 4 + 8 despite the raise;
    # hour 3 at the cut price, 1 + 8.
    assert [c.resource_amount for c in charges] == [Decimal(12), Decimal(12), Decimal(9)]
    assert charges[0].token_amount == Decimal(1)
    assert all(c.node_price_id is not None and c.rates["source"] == "node" for c in charges)
    assert all(c.platform_fee_rate == Decimal("0.1") for c in charges)
    total = sum(c.amount for c in charges)
    assert await _wallet(db, customer_user.id) == Decimal(5000) - total
    assert await _wallet(db, provider_user.id) == sum(c.provider_amount for c in charges)
    report = await reconciliation_service.report(db)
    assert report["ok"], report["issues"]


async def test_default_prices_apply_to_new_and_optionally_existing_machines(client, db, enroll_node, make_user):
    _, provider = await make_user("provider")
    before = await enroll_node(provider=provider)
    body = prices(cpu="2") | {"apply_to_existing": False}
    resp = await client.put("/api/v1/nodes/pricing/default", json=body, headers=provider)
    assert resp.status_code == 200 and resp.json()["updated_machines"] == 0
    assert (
        Decimal((await client.get("/api/v1/nodes/pricing/default", headers=provider)).json()["prices"]["cpu_core_hour"])
        == 2
    )

    after = await enroll_node(provider=provider)
    new_view = (await client.get(f"/api/v1/nodes/{after['node_id']}/pricing", headers=provider)).json()
    assert Decimal(new_view["charging"]["cpu_core_hour"]) == 2
    old_view = (await client.get(f"/api/v1/nodes/{before['node_id']}/pricing", headers=provider)).json()
    assert old_view["charging"] is None

    body = prices(cpu="3") | {"apply_to_existing": True}
    assert (await client.put("/api/v1/nodes/pricing/default", json=body, headers=provider)).json()[
        "updated_machines"
    ] == 2
    old_view = (await client.get(f"/api/v1/nodes/{before['node_id']}/pricing", headers=provider)).json()
    assert Decimal(old_view["charging"]["cpu_core_hour"]) == 3

    _, customer = await make_user("customer")
    assert (await client.put("/api/v1/nodes/pricing/default", json=body, headers=customer)).status_code == 403


async def test_market_shows_price_ranges_without_identifying_machines(client, db, enroll_node):
    await _network(db)
    cheap, dear = await enroll_node(), await enroll_node()
    await _set_price(client, cheap, cpu="2")
    await _set_price(client, dear, cpu="12")
    await enroll_node()  # charges the network prices
    market = (await client.get("/api/v1/billing/market")).json()
    assert market["nodes"] == 3 and market["own_prices"] == 2
    assert Decimal(market["ranges"]["cpu_core_hour"]["min"]) == 2
    assert Decimal(market["ranges"]["cpu_core_hour"]["max"]) == 12
    assert Decimal(market["commission_rate"]) == Decimal("0.1")
    assert cheap["node_id"] not in str(market) and dear["node_id"] not in str(market)


async def test_a_failed_deployment_only_moves_within_its_price_limits(client, db, enroll_node, make_user, ollama_model):
    await _network(db)
    cheap, dear, fair = await enroll_node(), await enroll_node(), await enroll_node()
    await _set_price(client, cheap, cpu="1")
    await _set_price(client, dear, cpu="60")  # above the network prices
    await _set_price(client, fair, cpu="5")
    _, customer = await _customer(client, make_user)
    dep = (await _deploy(client, customer, ollama_model)).json()
    assert dep["node_id"] == cheap["node_id"]

    def fail(node):
        return client.post(
            f"/api/v1/worker/deployments/{dep['id']}/status",
            json={"state": "FAILED", "error_code": "INSUFFICIENT_MEMORY", "message": "Out of memory"},
            headers=node["headers"],
        )

    async def current():
        return (await client.get(f"/api/v1/deployments/{dep['id']}", headers=customer)).json()

    await fail(cheap)
    moved = await current()
    assert moved["status"] == "SCHEDULED" and moved["node_id"] == fair["node_id"]
    await fail(fair)
    failed = await current()
    assert failed["status"] == "FAILED"  # the only machine left charges more than the limit
    assert "price limit" in failed["error_message"]
