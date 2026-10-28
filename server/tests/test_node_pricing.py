"""Per-machine prices: providers set them (in their own currency), placement picks the cheapest machine within the
customer's limits, and estimates never exceed the rates a deployment was placed at."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.timeutil import utcnow
from app.documents import AuditLog, CostEstimate, NodePrice, UsageRecord
from app.services import cost_service
from tests.test_cost_estimates import _set_ready_at


def prices(cpu="10", ram="20", vram="0", tin="1000", tout="2000", currency="NGN") -> dict:
    return {
        "currency": currency,
        "cpu_core_hour": cpu,
        "ram_gb_hour": ram,
        "vram_gb_hour": vram,
        "input_tokens_per_million": tin,
        "output_tokens_per_million": tout,
    }


async def _set_price(client, node, **over):
    resp = await client.put(
        f"/api/v1/nodes/{node['node_id']}/pricing", json=prices(**over), headers=node["provider_headers"]
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _deploy(client, headers, model, **body):
    return await client.post("/api/v1/deployments", json={"model_id": str(model.id), **body}, headers=headers)


async def test_providers_price_their_own_machines_only(client, db, enroll_node, make_user):
    node = await enroll_node()
    view = await client.get(f"/api/v1/nodes/{node['node_id']}/pricing", headers=node["provider_headers"])
    assert view.status_code == 200 and view.json()["charging"] is None and view.json()["history"] == []

    out = await _set_price(client, node, cpu="7.5", currency="USD")
    assert out["charging"]["currency"] == "USD" and Decimal(out["charging"]["cpu_core_hour"]) == Decimal("7.5")
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


@pytest.mark.parametrize(
    "bad",
    [{"cpu_core_hour": "-1"}, {"ram_gb_hour": "2000000"}, {"surprise": "1"}, {"currency": "naira"}, {"currency": ""}],
)
async def test_invalid_prices_are_refused(client, enroll_node, bad):
    node = await enroll_node()
    resp = await client.put(
        f"/api/v1/nodes/{node['node_id']}/pricing", json=prices() | bad, headers=node["provider_headers"]
    )
    assert resp.status_code == 422


async def test_placement_picks_the_cheapest_machine(client, db, enroll_node, make_user, ollama_model):
    dear, cheap, middle = await enroll_node(), await enroll_node(), await enroll_node()
    await _set_price(client, dear, cpu="9")
    await _set_price(client, cheap, cpu="3")
    await _set_price(client, middle, cpu="5")
    _, customer = await make_user("customer")

    quote = await client.post("/api/v1/deployments/quote", json={"model_id": str(ollama_model.id)}, headers=customer)
    assert quote.status_code == 200, quote.text
    q = quote.json()["by_runtime"][0]
    assert q["eligible_nodes"] == 3 and Decimal(q["hourly"]) == Decimal(3 + 20)
    assert q["provider"]["display_name"].startswith("Provider ")

    first = (await _deploy(client, customer, ollama_model)).json()
    assert first["node_id"] == cheap["node_id"]
    pricing = (await client.get(f"/api/v1/deployments/{first['id']}/pricing", headers=customer)).json()
    assert Decimal(pricing["hourly"]) == Decimal(23) and pricing["rates"]["currency"] == "NGN"
    assert pricing["provider"] is not None


async def test_a_free_machine_beats_any_priced_one(client, db, enroll_node, make_user, ollama_model):
    priced, free = await enroll_node(), await enroll_node()
    await _set_price(client, priced, cpu="1", ram="0")
    _, customer = await make_user("customer")
    dep = (await _deploy(client, customer, ollama_model)).json()
    assert dep["node_id"] == free["node_id"]


async def test_price_limits_and_currency_are_respected(client, db, enroll_node, make_user, ollama_model):
    ngn, usd = await enroll_node(), await enroll_node()
    await _set_price(client, ngn, cpu="50")  # 70 NGN/h for this reservation
    await _set_price(client, usd, cpu="1", currency="USD")
    _, customer = await make_user("customer")

    refused = await _deploy(client, customer, ollama_model, max_hourly_price="30")
    assert refused.status_code == 503
    assert refused.json()["detail"]["reasons"] == {"over_price_limit": 1, "other_currency": 1}
    assert "price limit" in refused.json()["detail"]["message"]

    raised = await _deploy(client, customer, ollama_model, max_hourly_price="100")
    assert raised.status_code == 201 and raised.json()["node_id"] == ngn["node_id"]
    in_usd = await _deploy(client, customer, ollama_model, currency="USD")
    assert in_usd.status_code == 201 and in_usd.json()["node_id"] == usd["node_id"]

    tokens = await enroll_node()
    await _set_price(client, tokens, cpu="0", ram="0", tout="9000")  # free per hour, dear per token
    q = (
        await client.post(
            "/api/v1/deployments/quote",
            json={"model_id": str(ollama_model.id), "max_token_price": "2000", "max_hourly_price": "1"},
            headers=customer,
        )
    ).json()["by_runtime"][0]
    assert q["eligible_nodes"] == 0 and q["over_price_limit"] == 2 and q["other_currency"] == 1


async def test_estimates_never_exceed_the_placement_rates(client, db, enroll_node, make_user, ollama_model):
    """A provider's rise applies only to new placements; a cut applies at once."""
    _, provider = await make_user("provider")
    node = await enroll_node(provider=provider)
    await _set_price(client, node, cpu="4", ram="8", tin="500", tout="500")
    await db.update_many(
        NodePrice, {"node_id": uuid.UUID(node["node_id"])}, {"$set": {"effective_from": utcnow() - timedelta(days=1)}}
    )
    await db.commit()
    _, customer = await make_user("customer")
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
    first = await db.find_one(NodePrice, {"node_id": uuid.UUID(node["node_id"])})
    for version, when, cpu in ((2, start + timedelta(hours=1), "40"), (3, start + timedelta(hours=2), "1")):
        db.add(
            NodePrice(
                node_id=first.node_id,
                provider_id=first.provider_id,
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

    assert await cost_service.run_estimates(start + timedelta(hours=3)) == 3
    estimates = await db.find(CostEstimate, sort=[("period_start", 1)])
    # Hour 1 at the placement rates (4 + 8); hour 2 still 4 + 8 despite the rise; hour 3 at the cut price, 1 + 8.
    assert [e.resource_amount for e in estimates] == [Decimal(12), Decimal(12), Decimal(9)]
    assert estimates[0].token_amount == Decimal(1)
    assert all(e.node_price_id is not None and e.currency == "NGN" for e in estimates)


async def test_default_prices_apply_to_new_and_optionally_existing_machines(client, db, enroll_node, make_user):
    _, provider = await make_user("provider")
    before = await enroll_node(provider=provider)
    body = prices(cpu="2", currency="EUR") | {"apply_to_existing": False}
    resp = await client.put("/api/v1/nodes/pricing/default", json=body, headers=provider)
    assert resp.status_code == 200 and resp.json()["updated_machines"] == 0
    stored = (await client.get("/api/v1/nodes/pricing/default", headers=provider)).json()["prices"]
    assert Decimal(stored["cpu_core_hour"]) == 2 and stored["currency"] == "EUR"

    after = await enroll_node(provider=provider)
    new_view = (await client.get(f"/api/v1/nodes/{after['node_id']}/pricing", headers=provider)).json()
    assert Decimal(new_view["charging"]["cpu_core_hour"]) == 2 and new_view["charging"]["currency"] == "EUR"
    old_view = (await client.get(f"/api/v1/nodes/{before['node_id']}/pricing", headers=provider)).json()
    assert old_view["charging"] is None

    body = prices(cpu="3") | {"apply_to_existing": True}
    updated = (await client.put("/api/v1/nodes/pricing/default", json=body, headers=provider)).json()
    assert updated["updated_machines"] == 2
    old_view = (await client.get(f"/api/v1/nodes/{before['node_id']}/pricing", headers=provider)).json()
    assert Decimal(old_view["charging"]["cpu_core_hour"]) == 3

    _, customer = await make_user("customer")
    assert (await client.put("/api/v1/nodes/pricing/default", json=body, headers=customer)).status_code == 403


async def test_market_shows_price_ranges_per_currency_without_identifying_machines(client, db, enroll_node):
    cheap, dear, usd = await enroll_node(), await enroll_node(), await enroll_node()
    await _set_price(client, cheap, cpu="2")
    await _set_price(client, dear, cpu="12")
    await _set_price(client, usd, cpu="1", currency="USD")
    await enroll_node()  # free
    market = (await client.get("/api/v1/billing/market")).json()
    assert market["nodes"] == 4 and market["free_nodes"] == 1
    ngn = next(c for c in market["currencies"] if c["currency"] == "NGN")
    assert ngn["nodes"] == 2
    assert Decimal(ngn["ranges"]["cpu_core_hour"]["min"]) == 2
    assert Decimal(ngn["ranges"]["cpu_core_hour"]["max"]) == 12
    for n in (cheap, dear, usd):
        assert n["node_id"] not in str(market)
