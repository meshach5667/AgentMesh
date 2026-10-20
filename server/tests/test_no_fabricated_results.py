"""The platform must never report inference success, or bill, without a real model runtime."""

from decimal import Decimal

from sqlalchemy import func, select

from app.core.security import get_password_hash
from app.models import Node, Provider, Transaction, User, Wallet


async def _online_node(db):
    user = User(email="p@example.com", hashed_password=get_password_hash("x" * 10), role="provider")
    db.add(user)
    await db.flush()
    provider = Provider(user_id=user.id)
    db.add(provider)
    await db.flush()
    db.add(Node(owner_id=provider.id, name="n", public_key="pem", status="ONLINE", api_key_hash="h"))
    await db.commit()


async def test_inference_without_runtime_fails_and_is_not_billed(client, db, make_user, approved_model):
    await _online_node(db)
    user, headers = await make_user("customer")
    db.add(Wallet(user_id=user.id, balance=Decimal("5")))
    await db.commit()

    resp = await client.post(
        "/api/v1/inference", json={"model": approved_model.name, "input": {"prompt": "hello"}}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["error_code"] == "NO_INFERENCE_ENDPOINT"
    assert body["result"] is None

    wallet = (await db.execute(select(Wallet).where(Wallet.user_id == user.id))).scalars().one()
    await db.refresh(wallet)
    assert wallet.balance == Decimal("5")
    assert (await db.execute(select(func.count(Transaction.id)))).scalar() == 0


async def test_agent_endpoints_do_not_claim_success(client):
    assert (await client.post("/api/v1/agent/deploy")).status_code == 501
