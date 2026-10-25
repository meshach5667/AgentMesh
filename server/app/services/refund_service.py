"""Refunds, issued by operators.

* Charge refund: (part of) a compute charge goes back to the customer's wallet. It is split like the charge was:
  the provider's share is taken back from the provider's wallet (REFUND_CLAWBACK, which may leave it negative if
  the money was already paid out; later earnings then cover it) and the commission is given up
  (PLATFORM_FEE_REVERSAL). The charge's refunded totals move with a compare-and-set, so concurrent refunds can never
  return more than was charged. Settles immediately.
* Top-up refund: wallet funds go back to the customer's card through Paystack. The amount is held (a PENDING
  TOPUP_REFUND debit, so it cannot be spent meanwhile) and settled when Paystack reports the refund processed, or
  released when it fails. Only money still in the wallet can be refunded, and never more than the payment.

Every refund is audited and reconciled (reconciliation_service).
"""

import secrets
import uuid
from decimal import Decimal
from typing import Any

from bson import Decimal128
from fastapi import HTTPException

from app.core.database import Session
from app.core.ids import parse_uuid
from app.core.timeutil import utcnow
from app.documents.billing import Charge, Payment, PaymentStatus, Refund, RefundKind, RefundStatus
from app.documents.transaction import Transaction, TransactionStatus, TransactionType
from app.documents.user import User
from app.documents.wallet import Wallet
from app.services import audit_service, ledger_service, paystack
from app.services.ledger_service import money
from app.services.paystack import PaystackError, from_subunits

CENT = Decimal("0.01")
ZERO = Decimal128("0")


def _reference() -> str:
    return f"am-rf-{secrets.token_hex(12)}"


def _reason(reason: str) -> str:
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="Give a reason for the refund (it is shown to the customer)")
    return reason[:300]


def split_refund(charge: Charge, amount: Decimal) -> tuple[Decimal, Decimal]:
    """(provider part, commission part) of refunding ``amount`` of ``charge``, in the charge's own proportions.
    The refund that empties the charge takes exactly what is left of each part, so rounding never drifts."""
    remaining = money(charge.amount) - money(charge.refunded_amount or 0)
    left_fee = money(charge.platform_fee) - money(charge.refunded_fee or 0)
    left_provider = money(charge.provider_amount) - money(charge.refunded_provider or 0)
    if amount == remaining:
        return left_provider, left_fee
    fee = min(money(amount * money(charge.platform_fee) / money(charge.amount)), left_fee)
    provider = amount - fee
    if provider > left_provider:
        provider = left_provider
        fee = amount - provider
    return provider, fee


async def refund_charge(db: Session, charge_id: str, amount: Decimal | None, reason: str, actor: User) -> Refund:
    reason = _reason(reason)
    charge = await db.get(Charge, parse_uuid(charge_id, "Charge"))
    if charge is None:
        raise HTTPException(status_code=404, detail="Charge not found")
    remaining = money(charge.amount) - money(charge.refunded_amount or 0)
    if remaining <= 0:
        raise HTTPException(status_code=409, detail="This charge has already been refunded in full")
    amount = remaining if amount is None else money(amount)
    if amount <= 0 or amount > remaining:
        raise HTTPException(
            status_code=422 if amount <= 0 else 409,
            detail=f"A refund of this charge must be more than 0 and at most {remaining} {charge.currency}",
        )
    provider_part, fee_part = split_refund(charge, amount)
    claimed = await db.update_one(
        Charge,
        {
            "_id": charge.id,
            "$expr": {
                "$lte": [{"$add": [{"$ifNull": ["$refunded_amount", Decimal128("0")]}, Decimal128(amount)]}, "$amount"]
            },
        },
        {
            "$inc": {
                "refunded_amount": Decimal128(amount),
                "refunded_fee": Decimal128(fee_part),
                "refunded_provider": Decimal128(provider_part),
            }
        },
    )
    if not claimed:
        raise HTTPException(status_code=409, detail="The charge was refunded concurrently; reload and try again")
    customer_wallet = await db.get(Wallet, charge.customer_wallet_id)
    provider_wallet = await db.get(Wallet, charge.provider_wallet_id) if charge.provider_wallet_id else None
    if customer_wallet is None:
        raise HTTPException(status_code=409, detail="The customer's wallet no longer exists")
    now = utcnow()
    refund = Refund(
        id=uuid.uuid4(),
        kind=RefundKind.CHARGE.value,
        reference=_reference(),
        user_id=customer_wallet.user_id,
        wallet_id=customer_wallet.id,
        charge_id=charge.id,
        provider_wallet_id=provider_wallet.id if provider_wallet else None,
        amount=amount,
        provider_amount=provider_part,
        platform_fee=fee_part,
        currency=charge.currency,
        reason=reason,
        status=RefundStatus.SUCCEEDED.value,
        requested_by=actor.id,
        completed_at=now,
    )
    db.add(refund)
    key = f"refund:{refund.reference}"
    credit = await ledger_service.post(
        db,
        key=f"{key}:credit",
        type=TransactionType.REFUND,
        amount=amount,
        to_wallet=customer_wallet,
        reference=refund.reference,
        deployment_id=charge.deployment_id,
        description=f"Refund: {reason}"[:300],
    )
    refund.transaction_id = credit.id
    if provider_wallet is not None and provider_part > 0:
        await ledger_service.post(
            db,
            key=f"{key}:clawback",
            type=TransactionType.REFUND_CLAWBACK,
            amount=provider_part,
            from_wallet=provider_wallet,
            reference=refund.reference,
            deployment_id=charge.deployment_id,
            description="Your share of a refunded charge",
        )
    if fee_part > 0:
        await ledger_service.post(
            db,
            key=f"{key}:fee",
            type=TransactionType.PLATFORM_FEE_REVERSAL,
            amount=fee_part,
            reference=refund.reference,
            deployment_id=charge.deployment_id,
            description="Platform commission on a refunded charge",
        )
    audit_service.record(
        db,
        actor_id=actor.id,
        action="refund.charge",
        resource_type="charge",
        resource_id=charge.id,
        details={
            "reference": refund.reference,
            "amount": str(amount),
            "provider_amount": str(provider_part),
            "platform_fee": str(fee_part),
            "reason": reason,
        },
    )
    await db.commit()
    await db.refresh(refund)
    return refund


async def refundable(db: Session, payment: Payment) -> Decimal:
    """What is left of a top-up after its refunds (pending or done)."""
    rows = await db.aggregate(
        Refund,
        [
            {"$match": {"payment_id": payment.id, "status": {"$ne": RefundStatus.FAILED.value}}},
            {"$group": {"_id": None, "amount": {"$sum": "$amount"}}},
        ],
    )
    return money(payment.amount) - (money(rows[0]["amount"]) if rows else Decimal(0))


async def refund_topup(db: Session, payment_id: str, amount: Decimal | None, reason: str, actor: User) -> Refund:
    from app.services.payments_service import _require_payments

    _require_payments()
    reason = _reason(reason)
    payment = await db.get(Payment, parse_uuid(payment_id, "Payment"))
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status != PaymentStatus.SUCCEEDED.value:
        raise HTTPException(
            status_code=409, detail=f"Only successful top-ups can be refunded (this one is {payment.status})"
        )
    if await db.count(Refund, {"payment_id": payment.id, "status": RefundStatus.PENDING.value}):
        raise HTTPException(status_code=409, detail="A refund of this top-up is already in progress")
    left = await refundable(db, payment)
    amount = left if amount is None else money(amount)
    if amount != amount.quantize(CENT):
        raise HTTPException(status_code=422, detail="Amounts can have at most 2 decimal places")
    if amount <= 0 or amount > left:
        raise HTTPException(status_code=409, detail=f"At most {left} {payment.currency} of this top-up can be refunded")
    wallet = await db.get(Wallet, payment.wallet_id)
    if wallet is None:
        raise HTTPException(status_code=409, detail="The customer's wallet no longer exists")
    refund = Refund(
        id=uuid.uuid4(),
        kind=RefundKind.TOPUP.value,
        reference=_reference(),
        user_id=payment.user_id,
        wallet_id=wallet.id,
        payment_id=payment.id,
        amount=amount,
        currency=payment.currency,
        reason=reason,
        requested_by=actor.id,
    )
    db.add(refund)
    hold = await ledger_service.post(
        db,
        key=f"refund:{refund.reference}",
        type=TransactionType.TOPUP_REFUND,
        status=TransactionStatus.PENDING,
        amount=amount,
        from_wallet=wallet,
        reference=refund.reference,
        description=f"Refund to your card of top-up {payment.reference}",
    )
    available = await ledger_service.balance(db, wallet.id)
    if available < 0:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"The customer has spent part of this top-up; at most {money(available + amount)} can be refunded",
        )
    refund.transaction_id = hold.id
    audit_service.record(
        db,
        actor_id=actor.id,
        action="refund.topup_requested",
        resource_type="payment",
        resource_id=payment.id,
        details={"reference": refund.reference, "amount": str(amount), "reason": reason},
    )
    await db.commit()  # held and recorded before Paystack is asked, so it is never refunded twice
    try:
        data = await paystack.create_refund(transaction_reference=payment.reference, amount=amount, note=reason)
    except PaystackError as exc:
        if exc.uncertain:
            refund.failure_reason = f"Outcome unknown, will be reconciled: {exc}"[:300]
        else:
            await _close(db, refund, RefundStatus.FAILED, f"Paystack refused the refund: {exc}"[:300])
        await db.commit()
        await db.refresh(refund)
        return refund
    refund.paystack_refund_id = str(data.get("id") or "")[:50] or None
    await apply_paystack_result(db, refund, data)
    await db.commit()
    await db.refresh(refund)
    return refund


async def _close(db: Session, refund: Refund, status: RefundStatus, reason: str | None) -> bool:
    """PENDING -> final, settling or releasing the hold. Does not commit."""
    moved = await db.update_one(
        Refund,
        {"_id": refund.id, "status": RefundStatus.PENDING.value},
        {"$set": {"status": status.value, "failure_reason": reason, "completed_at": utcnow()}},
    )
    if not moved:
        return False
    hold = await db.get(Transaction, refund.transaction_id) if refund.transaction_id else None
    if hold is not None:
        if status == RefundStatus.SUCCEEDED:
            await ledger_service.settle(db, hold)
        else:
            await ledger_service.fail(db, hold)
    await db.refresh(refund)
    audit_service.record(
        db,
        actor_id=None,
        action=f"refund.topup_{status.value.lower()}",
        resource_type="refund",
        resource_id=refund.id,
        details={"reference": refund.reference, "amount": str(refund.amount), "reason": reason},
    )
    return True


async def apply_paystack_result(db: Session, refund: Refund, data: dict[str, Any]) -> str:
    """Apply a Paystack refund record (create response, fetch, or webhook). Does not commit."""
    status = str(data.get("status") or "")
    refund.provider_status = status[:30] or None
    if refund.status != RefundStatus.PENDING.value:
        return f"already_{refund.status.lower()}"
    if data.get("amount") is not None:
        try:
            reported = from_subunits(data["amount"])
        except (TypeError, ValueError):
            reported = Decimal(-1)
        if reported != money(refund.amount):
            refund.failure_reason = f"Paystack reported {reported}; expected {refund.amount}. Needs review"
            return "amount_mismatch"
    if status == "processed":
        await _close(db, refund, RefundStatus.SUCCEEDED, None)
        return "succeeded"
    if status == "failed":
        await _close(db, refund, RefundStatus.FAILED, str(data.get("reason") or "Paystack could not refund")[:300])
        return "failed"
    return f"pending_{status or 'unknown'}"


async def handle_webhook_event(db: Session, event: str, data: dict[str, Any]) -> str:
    """A signed ``refund.*`` event. Matched to the open refund of the transaction it names. Does not commit."""
    reference = str(data.get("transaction_reference") or "")[:100]
    payment = await db.find_one(Payment, {"reference": reference}) if reference else None
    if payment is None:
        return "unknown_reference"
    refund = await db.find_one(Refund, {"payment_id": payment.id, "status": RefundStatus.PENDING.value})
    if refund is None:
        return "no_open_refund"
    status = {"refund.processed": "processed", "refund.failed": "failed"}.get(
        event, str(data.get("status") or "pending")
    )
    return await apply_paystack_result(db, refund, {**data, "status": status})


async def list_refunds(db: Session, user: User | None, status: str | None = None, limit: int = 200) -> list[Refund]:
    """A customer's refunds, or (user None) all of them for staff."""
    filter: dict[str, Any] = {}
    if user is not None:
        filter["user_id"] = user.id
    if status:
        filter["status"] = status
    return await db.find(Refund, filter, sort=[("created_at", -1)], limit=limit)
