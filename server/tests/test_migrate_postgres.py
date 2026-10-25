"""The PostgreSQL -> MongoDB copy script, fed rows shaped like asyncpg returns them."""

import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.mongo import Session
from app.documents import Node, Transaction, User, Wallet

spec = importlib.util.spec_from_file_location(
    "migrate_postgres_to_mongo", Path(__file__).resolve().parents[1] / "scripts" / "migrate_postgres_to_mongo.py"
)
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)  # type: ignore[union-attr]

USER_ID, WALLET_ID, NODE_ID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
WHEN = datetime(2026, 10, 1, 12, 0, 0, 123000)


def tables() -> dict[str, list[dict]]:
    return {
        "users": [
            {
                "id": USER_ID,
                "email": "p@example.com",
                "hashed_password": "x",
                "role": "provider",
                "is_active": True,
                "created_at": WHEN,
                "updated_at": WHEN.replace(tzinfo=UTC) + timedelta(hours=1),  # timestamptz comes back aware
            }
        ],
        "wallets": [
            {
                "id": WALLET_ID,
                "user_id": USER_ID,
                "balance": Decimal("12.50000000"),
                "currency": "NGN",
                "created_at": WHEN,
            }
        ],
        "transactions": [
            {
                "id": uuid.uuid4(),
                "from_wallet": None,
                "to_wallet": WALLET_ID,
                "amount": Decimal("12.5"),
                "type": "DEPOSIT",
                "status": "SETTLED",
                "deployment_id": None,
                "reference": "test-credit",
                "description": None,
                "created_at": WHEN,
                "idempotency_key": "k1",
                "settled_at": WHEN,
            }
        ],
        "nodes": [
            {
                "id": NODE_ID,
                "owner_id": uuid.uuid4(),
                "name": "n",
                "runtimes": [{"name": "ollama", "available": True}],  # jsonb, decoded by the codec
                "status": "ONLINE",
                "legacy_column": "dropped",
            }
        ],
    }


def source(data):
    async def rows(table):
        for row in data.get(table, []):
            yield dict(row)

    return rows


async def test_copies_rows_with_same_ids_and_values(mongo):
    logged = []
    counts = await script.migrate(source(tables()), set(tables()), replace=False, dry_run=False, log=logged.append)
    assert counts == {"nodes": 1, "transactions": 1, "users": 1, "wallets": 1}
    assert any("legacy_column" in line for line in logged)
    db = Session()
    user = await db.get(User, USER_ID)
    assert user.email == "p@example.com" and user.updated_at == WHEN + timedelta(hours=1)
    assert (await db.get(Wallet, WALLET_ID)).balance == Decimal("12.5")
    assert (await db.get(Node, NODE_ID)).runtimes == [{"name": "ollama", "available": True}]
    assert await db.count(Transaction, {"idempotency_key": "k1"}) == 1
    assert await script._reconcile(log=logged.append)


async def test_refuses_a_non_empty_target_unless_replacing(mongo):
    await script.migrate(source(tables()), set(tables()), replace=False, dry_run=False, log=lambda _: None)
    with pytest.raises(SystemExit, match="not empty"):
        await script.migrate(source(tables()), set(tables()), replace=False, dry_run=False, log=lambda _: None)
    changed = tables()
    changed["users"] = []
    await script.migrate(source(changed), set(changed), replace=True, dry_run=False, log=lambda _: None)
    assert await Session().count(User) == 0  # rows deleted in PostgreSQL disappear on a replacing copy
