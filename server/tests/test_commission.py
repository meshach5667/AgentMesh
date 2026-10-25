"""Platform commission: the configurable default rate, the per-charge split, eligibility, and fee breakdowns."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.config import settings
from app.core.timeutil import utcnow
from app.documents import Charge, UsageRecord
from app.documents.transaction import Transaction
from app.services import billing_service
from app.services.billing_service import split
from tests.test_billing import PRICES, _price, _ready_deployment, _set_ready_at, _wallet

NO_FEE = {k: v for k, v in PRICES.items() if k != "platform_fee_rate"}


@pytest.mark.parametrize("amount", ["1", "0.00000003", "123.45678901", "999999.99999999", "0"])
@pytest.mark.parametrize("rate", ["0.1", "0.0333", "0", "0.5"])
def test_split_always_adds_up(amount, rate):
    provider, fee = split(Decimal(amount), Decimal(rate))
    assert provider + fee == Decimal(amount) and fee >= 0 and provider >= 0


async def test_new_versions_default_to_ten_percent_and_respect_the_ceiling(client, make_user):
    _, operator = await make_user("operator")
    resp = await client.post("/api/v1/admin/pricing", json=NO_FEE, headers=operator)
    assert resp.status_code == 201, resp.text
    assert Decimal(resp.json()["platform_fee_rate"]) == settings.DEFAULT_PLATFORM_FEE_RATE == Decimal("0.10")
    too_high = await client.post("/api/v1/admin/pricing", json=NO_FEE | {"platform_fee_rate": "0.6"}, headers=operator)
    assert too_high.status_code == 422
    pricing = (await client.get("/api/v1/billing/pricing")).json()
    assert Decimal(pricing["default_platform_fee_rate"]) == Decimal("0.10")
    assert Decimal(pricing["max_platform_fee_rate"]) == Decimal("0.50")


async def test_ceiling_is_configurable(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "MAX_PLATFORM_FEE_RATE", Decimal("0.2"))
    _, operator = await make_user("operator")
    resp = await client.post("/api/v1/admin/pricing", json=NO_FEE | {"platform_fee_rate": "0.25"}, headers=operator)
    assert resp.status_code == 422 and "0.2" in resp.text


async def test_provider_gets_ninety_percent_and_the_ledger_records_the_fee(
    client, db, enroll_node, make_user, ollama_model
):
    await _price(db)  # platform_fee_rate 0.1
    provider_user, provider = await make_user("provider")
    dep, _, customer_user, customer = await _ready_deployment(
        client, db, enroll_node, make_user, ollama_model, provider=provider, credit="5000"
    )
    start = utcnow() - timedelta(hours=1)
    await _set_ready_at(db, dep["id"], start)
    await billing_service.run_billing(start + timedelta(hours=1))
    charge = await db.find_one(Charge)
    assert charge.platform_fee_rate == Decimal("0.1")
    assert charge.platform_fee == (charge.amount * Decimal("0.1")).quantize(Decimal("0.00000001"))
    assert charge.provider_amount == charge.amount - charge.platform_fee
    assert await _wallet(db, provider_user.id) == charge.provider_amount
    assert await _wallet(db, customer_user.id) == Decimal(5000) - charge.amount
    fee_entry = await db.find_one(Transaction, {"type": "PLATFORM_FEE", "reference": f"charge:{charge.id}"})
    assert fee_entry is not None and fee_entry.amount == charge.platform_fee

    out = (await client.get("/api/v1/billing/charges", headers=customer)).json()[0]
    assert Decimal(out["platform_fee_rate"]) == Decimal("0.1")
    assert Decimal(out["platform_fee"]) + Decimal(out["provider_amount"]) == Decimal(out["amount"])


async def test_only_successful_requests_are_billed_for_tokens(client, db, enroll_node, make_user, ollama_model):
    await _price(db, cpu_core_hour="0", ram_gb_hour="0")
    dep, node, *_ = await _ready_deployment(client, db, enroll_node, make_user, ollama_model)
    start = utcnow() - timedelta(hours=1)
    await _set_ready_at(db, dep["id"], start)
    for outcome, tokens in (("success", 100_000), ("runtime_error", 900_000), ("timeout", 900_000), (None, 900_000)):
        db.add(
            UsageRecord(
                kind="inference",
                outcome=outcome,
                deployment_id=uuid.UUID(dep["id"]),
                node_id=uuid.UUID(node["node_id"]),
                request_id=uuid.uuid4().hex,
                input_tokens=tokens,
                output_tokens=0,
                created_at=start + timedelta(minutes=1),
            )
        )
    await db.commit()
    await billing_service.run_billing(start + timedelta(hours=1))
    charge = await db.find_one(Charge)
    assert charge.input_tokens == 100_000
    assert charge.token_amount == Decimal(100)  # 0.1M x 1000 per million


async def test_commission_change_keeps_prices_and_is_audited(client, db, make_user):
    customer_user, customer = await make_user("customer")
    _, operator = await make_user("operator")
    none_yet = await client.post("/api/v1/admin/commission", json={"platform_fee_rate": "0.15"}, headers=operator)
    assert none_yet.status_code == 409
    await _price(db)
    assert (
        await client.post("/api/v1/admin/commission", json={"platform_fee_rate": "0.15"}, headers=customer)
    ).status_code == 403

    resp = await client.post("/api/v1/admin/commission", json={"platform_fee_rate": "0.15"}, headers=operator)
    assert resp.status_code == 201, resp.text
    new = resp.json()
    assert new["version"] == 2 and Decimal(new["platform_fee_rate"]) == Decimal("0.15")
    assert all(Decimal(new[k]) == Decimal(v) for k, v in NO_FEE.items())
    current = (await client.get("/api/v1/billing/pricing")).json()["current"]
    assert current["version"] == 2

    audit = (await client.get("/api/v1/admin/audit-logs?action=pricing.version_created", headers=operator)).json()
    assert audit[0]["details"]["platform_fee_rate"] == "0.15"

    later = (utcnow() + timedelta(days=1)).isoformat()
    await client.post("/api/v1/admin/pricing", json=PRICES | {"effective_from": later}, headers=operator)
    scheduled = await client.post("/api/v1/admin/commission", json={"platform_fee_rate": "0.2"}, headers=operator)
    assert scheduled.status_code == 409 and "scheduled" in scheduled.text


async def test_fee_breakdown_summaries_by_role(client, db, enroll_node, make_user, ollama_model):
    await _price(db)
    _, provider = await make_user("provider")
    dep, _, _, customer = await _ready_deployment(
        client, db, enroll_node, make_user, ollama_model, provider=provider, credit="5000"
    )
    start = utcnow() - timedelta(hours=2)
    await _set_ready_at(db, dep["id"], start)
    await billing_service.run_billing(start + timedelta(hours=2))
    charge = await db.find_one(Charge)
    _, operator = await make_user("operator")

    mine = (await client.get("/api/v1/billing/summary", headers=customer)).json()
    assert mine["scope"] == "customer" and mine["totals"]["charges"] == 1
    t = mine["totals"]
    assert Decimal(t["gross"]) == charge.amount and Decimal(t["platform_fee"]) == charge.platform_fee
    assert Decimal(t["gross"]) == Decimal(t["platform_fee"]) + Decimal(t["provider_share"])
    assert Decimal(t["effective_fee_rate"]) == Decimal("0.1")

    earned = (await client.get("/api/v1/billing/summary", headers=provider)).json()
    assert earned["scope"] == "provider" and Decimal(earned["totals"]["provider_share"]) == charge.provider_amount
    earnings = (await client.get("/api/v1/earnings", headers=provider)).json()
    assert Decimal(earnings["gross_earnings"]) == charge.amount
    assert Decimal(earnings["platform_fees"]) == charge.platform_fee

    network = (await client.get("/api/v1/billing/summary?scope=network", headers=operator)).json()
    assert Decimal(network["totals"]["platform_fee"]) == charge.platform_fee
    assert (await client.get("/api/v1/billing/summary?scope=network", headers=customer)).status_code == 403

    old = (await client.get("/api/v1/billing/summary?days=1", headers=customer)).json()
    assert old["totals"]["charges"] == 1  # the charge was rated just now
    empty = (await client.get("/api/v1/billing/summary", headers=(await make_user("customer"))[1])).json()
    assert Decimal(empty["totals"]["gross"]) == 0
    assert empty["totals"]["effective_fee_rate"] is None
