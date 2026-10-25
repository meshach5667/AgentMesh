"""The ledger: the only code that changes wallet balances.

Rules (checked by reconciliation_service):

* A debit (``from_wallet``) applies while the entry is PENDING or SETTLED; a credit (``to_wallet``) applies
  only when SETTLED. So: balance = settled credits - (pending + settled) debits.
* Balances change with an atomic ``$inc`` in the caller's transaction, never by read-modify-write, so
  concurrent postings cannot lose updates.
* Every posting carries an idempotency key (unique in the database). Posting the same key twice returns the
  existing entry and changes nothing.
* All amounts are in settings.BILLING_CURRENCY; a wallet in another currency is refused.

Nothing here commits.
"""

import uuid
from decimal import ROUND_HALF_UP, Decimal

from bson import Decimal128
from fastapi import HTTPException

from app.core.config import settings
from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.transaction import Transaction, TransactionStatus, TransactionType
from app.documents.wallet import Wallet

QUANTUM = Decimal("0.00000001")
DEBIT_STATES = (TransactionStatus.PENDING.value, TransactionStatus.SETTLED.value)


def money(value: Decimal | Decimal128 | int | str | float) -> Decimal:
    if isinstance(value, Decimal128):
        value = value.to_decimal()
    return Decimal(str(value)).quantize(QUANTUM, rounding=ROUND_HALF_UP)


async def wallet_for_user(db: Session, user_id: uuid.UUID) -> Wallet:
    """The user's wallet, created in the billing currency if missing. Does not commit."""
    wallet = await db.find_one(Wallet, {"user_id": user_id})
    if wallet is None:
        wallet = Wallet(id=uuid.uuid4(), user_id=user_id, balance=Decimal(0), currency=settings.BILLING_CURRENCY)
        db.add(wallet)
        await db.flush()  # the unique user_id index rejects a concurrently created second wallet
    return wallet


def _check_currency(wallet: Wallet | None) -> None:
    if wallet is not None and (wallet.currency or settings.BILLING_CURRENCY) != settings.BILLING_CURRENCY:
        raise HTTPException(
            status_code=409,
            detail=f"Wallet currency {wallet.currency} differs from the billing currency {settings.BILLING_CURRENCY}",
        )


async def _adjust(db: Session, wallet_id: uuid.UUID, delta: Decimal) -> None:
    await db.update_one(Wallet, {"_id": wallet_id}, {"$inc": {"balance": Decimal128(delta)}})


async def _existing(db: Session, key: str) -> Transaction | None:
    return await db.find_one(Transaction, {"idempotency_key": key})


async def post(
    db: Session,
    *,
    key: str,
    type: TransactionType,
    amount: Decimal,
    status: TransactionStatus = TransactionStatus.SETTLED,
    from_wallet: Wallet | None = None,
    to_wallet: Wallet | None = None,
    reference: str | None = None,
    description: str | None = None,
    deployment_id: uuid.UUID | None = None,
) -> Transaction:
    """Record one ledger entry and apply its balance effects. Idempotent on ``key``."""
    existing = await _existing(db, key)
    if existing is not None:
        return existing
    amount = money(amount)
    if amount < 0:
        raise ValueError("Ledger amounts are never negative; the direction is given by the wallets")
    _check_currency(from_wallet)
    _check_currency(to_wallet)
    tx = Transaction(
        id=uuid.uuid4(),
        idempotency_key=key,
        type=type.value,
        status=status.value,
        amount=amount,
        from_wallet=from_wallet.id if from_wallet else None,
        to_wallet=to_wallet.id if to_wallet else None,
        reference=reference,
        description=description,
        deployment_id=deployment_id,
        settled_at=utcnow() if status == TransactionStatus.SETTLED else None,
    )
    db.add(tx)
    await db.flush()  # the unique key rejects a concurrent duplicate before balances move
    if from_wallet is not None and status.value in DEBIT_STATES:
        await _adjust(db, from_wallet.id, -amount)
    if to_wallet is not None and status == TransactionStatus.SETTLED:
        await _adjust(db, to_wallet.id, amount)
    return tx


async def settle(db: Session, tx: Transaction) -> bool:
    """PENDING -> SETTLED. The debit already applied; the credit applies now. False if not PENDING."""
    now = utcnow()
    moved = await db.update_one(
        Transaction,
        {"_id": tx.id, "status": TransactionStatus.PENDING.value},
        {"$set": {"status": TransactionStatus.SETTLED.value, "settled_at": now}},
    )
    if not moved:
        return False
    if tx.to_wallet is not None:
        await _adjust(db, tx.to_wallet, money(tx.amount))
    _mark(tx, status=TransactionStatus.SETTLED.value, settled_at=now)
    return True


async def fail(db: Session, tx: Transaction) -> bool:
    """PENDING -> FAILED: the held debit is returned to the payer. False if not PENDING."""
    moved = await db.update_one(
        Transaction,
        {"_id": tx.id, "status": TransactionStatus.PENDING.value},
        {"$set": {"status": TransactionStatus.FAILED.value}},
    )
    if not moved:
        return False
    if tx.from_wallet is not None:
        await _adjust(db, tx.from_wallet, money(tx.amount))
    _mark(tx, status=TransactionStatus.FAILED.value)
    return True


def _mark(tx: Transaction, **values) -> None:
    """Mirror an atomic update onto the in-memory entry without making it look unsaved."""
    for name, value in values.items():
        setattr(tx, name, value)
    tx._save_state()


async def balance(db: Session, wallet_id: uuid.UUID) -> Decimal:
    rows = await db.aggregate(Wallet, [{"$match": {"_id": wallet_id}}, {"$project": {"balance": 1}}])
    return money(rows[0]["balance"]) if rows and rows[0].get("balance") is not None else Decimal(0)
