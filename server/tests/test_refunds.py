"""Phase 2: refunds (charge refunds and Paystack top-up refunds), transaction history, and revenue analytics."""

import asyncio
import csv
import io
import uuid
from datetime import timedelta
from decimal import Decimal

import httpx

from app.core.timeutil import utcnow
from app.documents import Charge, Refund, Transaction
from app.documents.transaction import TransactionType
from app.services import billing_service, ledger_service, reconciliation_service
from tests.test_billing import _price, _ready_deployment, _set_ready_at, _wallet
from tests.test_payments_paystack import balance, fake, topup, webhook  # noqa: F401  (fake is a fixture)


async def _charged(client, db, enroll_node, make_user, ollama_model, hours=2):
    """A settled charge between a customer and a provider at 10% commission."""
    await _price(db)
    provider_user, provider = await make_user("provider")
    dep, _, customer_user, customer = await _ready_deployment(
        client, db, enroll_node, make_user, ollama_model, provider=provider, credit="5000"
    )
    start = utcnow() - timedelta(hours=hours)
    await _set_ready_at(db, dep["id"], start)
    await billing_service.run_billing(start + timedelta(hours=hours))
    charge = await db.find_one(Charge)
    _, operator = await make_user("operator")
    return charge, (customer_user, customer), (provider_user, provider), operator


async def _refund(client, charge_id, headers, amount=None, reason="Model returned errors"):
    body = {"reason": reason} | ({"amount": str(amount)} if amount is not None else {})
    return await client.post(f"/api/v1/admin/refunds/charges/{charge_id}", json=body, headers=headers)


async def test_full_charge_refund_reverses_both_shares(client, db, enroll_node, make_user, ollama_model):
    charge, (cust_user, customer), (prov_user, provider), operator = await _charged(
        client, db, enroll_node, make_user, ollama_model
    )
    customer_before = await _wallet(db, cust_user.id)
    provider_before = await _wallet(db, prov_user.id)

    assert (await _refund(client, charge.id, customer)).status_code == 403
    assert (await _refund(client, charge.id, operator, reason="")).status_code == 422
    resp = await _refund(client, charge.id, operator)
    assert resp.status_code == 201, resp.text
    refund = resp.json()
    assert refund["status"] == "SUCCEEDED" and refund["kind"] == "charge"
    assert Decimal(refund["amount"]) == charge.amount
    assert Decimal(refund["provider_amount"]) == charge.provider_amount
    assert Decimal(refund["platform_fee"]) == charge.platform_fee

    assert await _wallet(db, cust_user.id) == customer_before + charge.amount
    assert await _wallet(db, prov_user.id) == provider_before - charge.provider_amount
    reversal = await db.find_one(Transaction, {"type": TransactionType.PLATFORM_FEE_REVERSAL.value})
    assert reversal.amount == charge.platform_fee and reversal.reference == refund["reference"]

    again = await _refund(client, charge.id, operator)
    assert again.status_code == 409
    report = await reconciliation_service.report(db)
    assert report["ok"], report["issues"]

    mine = (await client.get("/api/v1/billing/refunds", headers=customer)).json()
    assert [r["reference"] for r in mine] == [refund["reference"]] and mine[0]["reason"] == "Model returned errors"
    audit = (await client.get("/api/v1/admin/audit-logs?action=refund.charge", headers=operator)).json()
    assert audit[0]["details"]["reference"] == refund["reference"]
    listed = (await client.get("/api/v1/billing/charges", headers=customer)).json()[0]
    assert Decimal(listed["refunded_amount"]) == charge.amount


async def test_partial_refunds_add_up_exactly(client, db, enroll_node, make_user, ollama_model):
    charge, _, _, operator = await _charged(client, db, enroll_node, make_user, ollama_model)
    third = (charge.amount / 3).quantize(Decimal("0.00000001"))
    for _ in range(2):
        assert (await _refund(client, charge.id, operator, third)).status_code == 201
    too_much = await _refund(client, charge.id, operator, charge.amount)
    assert too_much.status_code == 409
    assert (await _refund(client, charge.id, operator)).status_code == 201  # the rest
    db.expire_all()
    refunds = await db.find(Refund, {"charge_id": charge.id})
    assert sum(money(r.amount) for r in refunds) == charge.amount
    assert sum(money(r.platform_fee) for r in refunds) == charge.platform_fee
    assert sum(money(r.provider_amount) for r in refunds) == charge.provider_amount
    assert (await reconciliation_service.report(db))["ok"]


def money(v) -> Decimal:
    return ledger_service.money(v)


async def test_concurrent_refunds_never_exceed_the_charge(client, db, enroll_node, make_user, ollama_model):
    charge, (cust_user, _), _, operator = await _charged(client, db, enroll_node, make_user, ollama_model)
    before = await _wallet(db, cust_user.id)
    results = await asyncio.gather(*[_refund(client, charge.id, operator) for _ in range(4)])
    assert sorted(r.status_code for r in results) == [201, 409, 409, 409]
    assert await _wallet(db, cust_user.id) == before + charge.amount
    assert (await reconciliation_service.report(db))["ok"]


async def _paid_topup(client, db, make_user, amount="2500"):
    user, customer = await make_user("customer")
    payment = await topup(client, customer, amount)
    subunits = int(Decimal(amount) * 100)
    data = {
        "id": payment["reference"],
        "reference": payment["reference"],
        "status": "success",
        "amount": subunits,
        "currency": "NGN",
    }
    await webhook(client, {"event": "charge.success", "data": data})
    assert await balance(db, user.id) == Decimal(amount)
    _, operator = await make_user("operator")
    return user, customer, operator, payment


async def test_topup_refund_is_held_then_settled_by_webhook(client, db, make_user, fake):  # noqa: F811
    user, customer, operator, payment = await _paid_topup(client, db, make_user)
    listed = (await client.get("/api/v1/admin/topups", headers=operator)).json()
    assert Decimal(next(p for p in listed if p["id"] == payment["id"])["refundable"]) == Decimal(2500)

    resp = await client.post(
        f"/api/v1/admin/refunds/topups/{payment['id']}",
        json={"amount": "1000", "reason": "Duplicate top-up"},
        headers=operator,
    )
    assert resp.status_code == 201, resp.text
    refund = resp.json()
    assert refund["status"] == "PENDING"
    assert (
        "POST",
        "/refund",
        {"transaction": payment["reference"], "amount": 100000, "merchant_note": "Duplicate top-up"},
    ) in fake.calls
    assert await balance(db, user.id) == Decimal(1500)  # held at once
    second = await client.post(
        f"/api/v1/admin/refunds/topups/{payment['id']}", json={"reason": "again"}, headers=operator
    )
    assert second.status_code == 409  # one at a time

    event = {"transaction_reference": payment["reference"], "status": "processed", "amount": 100000}
    assert (await webhook(client, {"event": "refund.processed", "data": event})).status_code == 200
    db.expire_all()
    stored = await db.find_one(Refund, {"reference": refund["reference"]})
    assert stored.status == "SUCCEEDED"
    assert await balance(db, user.id) == Decimal(1500)
    assert (await reconciliation_service.report(db))["ok"]

    rest = await client.post(
        f"/api/v1/admin/refunds/topups/{payment['id']}", json={"amount": "1600", "reason": "x x"}, headers=operator
    )
    assert rest.status_code == 409  # only 1500 of the payment is left


async def test_failed_topup_refund_returns_the_funds(client, db, make_user, fake):  # noqa: F811
    user, _, operator, payment = await _paid_topup(client, db, make_user)
    fake.refund_reply = {"status": "failed"}
    resp = await client.post(
        f"/api/v1/admin/refunds/topups/{payment['id']}", json={"reason": "Customer asked"}, headers=operator
    )
    assert resp.json()["status"] == "FAILED"
    assert await balance(db, user.id) == Decimal(2500)

    fake.refund_reply = {"status": "pending"}
    resp = await client.post(
        f"/api/v1/admin/refunds/topups/{payment['id']}", json={"reason": "Customer asked"}, headers=operator
    )
    assert resp.json()["status"] == "PENDING" and await balance(db, user.id) == 0
    event = {"transaction_reference": payment["reference"], "status": "failed"}
    await webhook(client, {"event": "refund.failed", "data": event})
    assert await balance(db, user.id) == Decimal(2500)
    assert (await reconciliation_service.report(db))["ok"]


async def test_spent_money_cannot_be_refunded_to_the_card(client, db, make_user, fake):  # noqa: F811
    user, _, operator, payment = await _paid_topup(client, db, make_user)
    wallet = await ledger_service.wallet_for_user(db, user.id)
    await ledger_service.post(
        db, key="spend", type=TransactionType.COMPUTE_CHARGE, amount=Decimal(2000), from_wallet=wallet
    )
    await db.commit()
    resp = await client.post(
        f"/api/v1/admin/refunds/topups/{payment['id']}",
        json={"amount": "1000", "reason": "Customer asked"},
        headers=operator,
    )
    assert resp.status_code == 409 and "500" in resp.text
    assert await balance(db, user.id) == Decimal(500)
    assert not any(c[1] == "/refund" for c in fake.calls)


async def test_uncertain_refund_is_reconciled(client, db, make_user, fake):  # noqa: F811
    user, _, operator, payment = await _paid_topup(client, db, make_user)
    resp = await client.post(
        f"/api/v1/admin/refunds/topups/{payment['id']}", json={"reason": "Customer asked"}, headers=operator
    )
    refund_id = str(resp.json()["id"])
    rid = next(iter(fake.refunds))
    fake.refunds[rid]["status"] = "processed"
    await db.update_many(Refund, {}, {"$set": {"created_at": utcnow() - timedelta(hours=2)}})
    await db.commit()
    result = await reconciliation_service.run()
    assert list(result["refunds"].values()) == ["succeeded"]
    db.expire_all()
    assert (await db.get(Refund, uuid.UUID(refund_id))).status == "SUCCEEDED"

    fake.refund_reply = httpx.ReadTimeout("slow")
    _, _, operator2, payment2 = await _paid_topup(client, db, make_user, "1000")
    timed_out = await client.post(
        f"/api/v1/admin/refunds/topups/{payment2['id']}", json={"reason": "Customer asked"}, headers=operator2
    )
    assert timed_out.json()["status"] == "PENDING" and "reconciled" in timed_out.json()["failure_reason"]
    issues = (await reconciliation_service.report(db))["issues"]
    assert [i["kind"] for i in issues] == ["refund_unverifiable"]


async def test_transaction_history_filters_direction_and_csv(client, db, enroll_node, make_user, ollama_model):
    charge, (cust_user, customer), (_, provider), operator = await _charged(
        client, db, enroll_node, make_user, ollama_model
    )
    await _refund(client, charge.id, operator, reason="Requested by the customer")
    wallet = await ledger_service.wallet_for_user(db, cust_user.id)
    await ledger_service.post(
        db,
        key="formula",
        type=TransactionType.DEPOSIT,
        amount=Decimal(1),
        to_wallet=wallet,
        description="=HYPERLINK(x)",
    )
    await db.commit()
    rows = (await client.get("/api/v1/transactions", headers=customer)).json()
    kinds = {(r["type"], r["direction"]) for r in rows}
    assert {("DEPOSIT", "credit"), ("COMPUTE_CHARGE", "debit"), ("REFUND", "credit")} <= kinds
    only = (await client.get("/api/v1/transactions?type=REFUND", headers=customer)).json()
    assert [r["type"] for r in only] == ["REFUND"]
    page = (await client.get("/api/v1/transactions?limit=1&offset=1", headers=customer)).json()
    assert len(page) == 1 and page[0]["id"] == rows[1]["id"]
    clawed = (await client.get("/api/v1/transactions?type=REFUND_CLAWBACK", headers=provider)).json()
    assert clawed[0]["direction"] == "debit"

    resp = await client.get("/api/v1/transactions/export.csv", headers=customer)
    assert resp.headers["content-type"].startswith("text/csv")
    table = list(csv.reader(io.StringIO(resp.text)))
    assert table[0][:4] == ["date_utc", "type", "direction", "amount"] and len(table) == len(rows) + 1
    formula_row = next(r for r in table if "HYPERLINK" in r[6])
    assert formula_row[6] == "'=HYPERLINK(x)"  # cannot run as a spreadsheet formula
    ledger = (await client.get("/api/v1/admin/transactions?type=PLATFORM_FEE_REVERSAL", headers=operator)).json()
    assert len(ledger) == 1


async def test_revenue_analytics_by_role(client, db, enroll_node, make_user, ollama_model):
    charge, (_, customer), (_, provider), operator = await _charged(client, db, enroll_node, make_user, ollama_model)
    half = (charge.amount / 2).quantize(Decimal("0.00000001"))
    await _refund(client, charge.id, operator, half)

    mine = (await client.get("/api/v1/analytics/revenue?days=7", headers=customer)).json()
    assert mine["scope"] == "customer" and len(mine["series"]) == 8
    t = mine["totals"]
    assert Decimal(t["gross"]) == charge.amount and Decimal(t["refunded"]) == half
    assert Decimal(t["net_customer_spend"]) == charge.amount - half
    assert mine["breakdown_by"] == "deployment" and mine["breakdown"][0]["label"] == "qwen2.5:0.5b"

    earned = (await client.get("/api/v1/analytics/revenue", headers=provider)).json()
    assert Decimal(earned["totals"]["net_provider_earnings"]) == charge.provider_amount - Decimal(
        earned["totals"]["clawback"]
    )
    assert earned["breakdown_by"] == "node"

    network = (await client.get("/api/v1/analytics/revenue?scope=network", headers=operator)).json()
    nt = network["totals"]
    assert Decimal(nt["net_platform_commission"]) == charge.platform_fee - Decimal(nt["fee_reversed"])
    assert Decimal(nt["platform_revenue"]) == Decimal(nt["net_platform_commission"]) + Decimal(nt["sponsorship"])
    assert {"topups", "payouts", "card_refunds", "sponsorship"} <= set(network["series"][-1])
    assert (await client.get("/api/v1/analytics/revenue?scope=network", headers=customer)).status_code == 403
