"""Paystack top-ups, webhooks, and provider payouts.

Money is credited only on a verified Paystack success whose amount and currency match what we asked for, and
exactly once: the payment row moves INITIALIZED -> SUCCEEDED with a compare-and-set, and the ledger posting
has a unique idempotency key. Webhook redeliveries are recorded once in payment_events and otherwise ignored.

Payouts hold the amount (a PENDING ledger debit) when requested. The hold is released (FAILED entry) only when
Paystack says the transfer failed or was reversed, or an operator rejects it; an unknown outcome (timeout) stays
PENDING until reconciliation asks Paystack.
"""

import logging
import secrets
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.billing import Payment, PaymentEvent, PaymentStatus, Payout, PayoutAccount, PayoutStatus
from app.documents.transaction import Transaction, TransactionStatus, TransactionType
from app.documents.user import User
from app.services import audit_service, ledger_service, paystack
from app.services.ledger_service import money
from app.services.paystack import PaystackError, from_subunits

logger = logging.getLogger(__name__)

OPEN_PAYMENT = [PaymentStatus.INITIALIZED.value]
OPEN_PAYOUT = [PayoutStatus.REQUESTED.value, PayoutStatus.PENDING.value, PayoutStatus.OTP_REQUIRED.value]


def _require_payments() -> None:
    if not settings.payments_enabled:
        raise HTTPException(status_code=503, detail="Payments are not configured on this AgentMesh network")


def _gateway_error(exc: PaystackError) -> HTTPException:
    return HTTPException(status_code=502, detail=f"Paystack: {exc}")


def payments_config() -> dict[str, Any]:
    return {
        "enabled": settings.payments_enabled,
        "provider": "paystack" if settings.payments_enabled else None,
        "mode": settings.payments_mode,
        "currency": settings.BILLING_CURRENCY,
        "topup_min": str(settings.TOPUP_MIN_AMOUNT),
        "topup_max": str(settings.TOPUP_MAX_AMOUNT),
        "payout_min": str(settings.PAYOUT_MIN_AMOUNT),
        "payouts_require_approval": settings.PAYOUTS_REQUIRE_APPROVAL,
        "test_credits": settings.test_credits_enabled,
    }


# --- Top-ups -----------------------------------------------------------------------------------------------


async def create_topup(db: Session, user: User, amount: Decimal) -> Payment:
    _require_payments()
    amount = money(amount)
    if amount != amount.quantize(Decimal("0.01")):
        raise HTTPException(status_code=422, detail="Amounts can have at most 2 decimal places")
    if not settings.TOPUP_MIN_AMOUNT <= amount <= settings.TOPUP_MAX_AMOUNT:
        raise HTTPException(
            status_code=422,
            detail=f"Top-ups must be between {settings.TOPUP_MIN_AMOUNT} and {settings.TOPUP_MAX_AMOUNT} "
            f"{settings.BILLING_CURRENCY}",
        )
    wallet = await ledger_service.wallet_for_user(db, user.id)
    payment = Payment(
        id=uuid.uuid4(),
        user_id=user.id,
        wallet_id=wallet.id,
        provider="paystack",
        reference=f"am-top-{secrets.token_hex(12)}",
        amount=amount,
        currency=settings.BILLING_CURRENCY,
        status=PaymentStatus.INITIALIZED.value,
    )
    db.add(payment)
    await db.commit()  # the reference exists before Paystack does, so a webhook can always find it
    try:
        data = await paystack.initialize_transaction(
            email=user.email,
            amount=amount,
            currency=payment.currency,
            reference=payment.reference,
            callback_url=f"{settings.FRONTEND_URL.rstrip('/')}/customer/wallet",
        )
    except PaystackError as exc:
        payment.status = PaymentStatus.FAILED.value
        payment.failure_reason = f"Checkout could not be created: {exc}"[:300]
        await db.commit()
        raise _gateway_error(exc) from None
    payment.authorization_url = str(data.get("authorization_url") or "")[:500] or None
    audit_service.record(
        db,
        actor_id=user.id,
        action="payment.topup_initialized",
        resource_type="payment",
        resource_id=payment.id,
        details={"amount": str(amount), "currency": payment.currency, "reference": payment.reference},
    )
    await db.commit()
    await db.refresh(payment)
    return payment


async def apply_paystack_result(db: Session, payment: Payment, data: dict[str, Any], source: str) -> str:
    """Apply a Paystack transaction record (from verify or a signed webhook) to a payment. Does not commit.
    Returns an outcome label."""
    status = str(data.get("status") or "")
    payment.provider_status = status[:30] or None
    if payment.status != PaymentStatus.INITIALIZED.value:
        return f"already_{payment.status.lower()}"
    if status == "success":
        try:
            paid = from_subunits(data.get("amount") or 0)
        except (TypeError, ValueError):
            paid = Decimal(-1)
        currency = str(data.get("currency") or "")
        if paid != Decimal(payment.amount) or currency != payment.currency:
            payment.status = PaymentStatus.REVIEW.value
            payment.failure_reason = (
                f"Paystack reported {paid} {currency}; expected {payment.amount} {payment.currency}"
            )
            audit_service.record(
                db,
                actor_id=None,
                action="payment.amount_mismatch",
                resource_type="payment",
                resource_id=payment.id,
                details={"reported": f"{paid} {currency}", "expected": f"{payment.amount} {payment.currency}"},
            )
            return "amount_mismatch"
        return await _credit(db, payment, data, source)
    if status in ("failed", "abandoned", "reversed"):
        moved = await db.update_one(
            Payment,
            {"_id": payment.id, "status": {"$in": OPEN_PAYMENT}},
            {
                "$set": {
                    "status": PaymentStatus.ABANDONED.value if status == "abandoned" else PaymentStatus.FAILED.value,
                    "failure_reason": str(data.get("gateway_response") or status)[:300],
                    "verified_at": utcnow(),
                }
            },
        )
        await db.refresh(payment)
        return status if moved else "already_closed"
    return f"still_{status or 'unknown'}"


async def _credit(db: Session, payment: Payment, data: dict[str, Any], source: str) -> str:
    now = utcnow()
    moved = await db.update_one(
        Payment,
        {"_id": payment.id, "status": {"$in": OPEN_PAYMENT}},
        {"$set": {"status": PaymentStatus.SUCCEEDED.value, "verified_at": now, "paid_at": now}},
    )
    if not moved:
        return "already_credited"
    wallet = await ledger_service.wallet_for_user(db, payment.user_id)
    tx = await ledger_service.post(
        db,
        key=f"payment:{payment.reference}",
        type=TransactionType.DEPOSIT,
        amount=Decimal(payment.amount),
        to_wallet=wallet,
        reference=payment.reference,
        description=f"Paystack top-up ({settings.payments_mode} mode)",
    )
    await db.update_one(
        Payment,
        {"_id": payment.id},
        {"$set": {"transaction_id": tx.id, "channel": str(data.get("channel") or "")[:30] or None}},
    )
    audit_service.record(
        db,
        actor_id=None,
        action="payment.credited",
        resource_type="payment",
        resource_id=payment.id,
        details={"amount": str(payment.amount), "via": source, "reference": payment.reference},
    )
    await db.refresh(payment)
    return "credited"


async def verify_topup(db: Session, user: User, reference: str) -> Payment:
    """Called when the customer returns from checkout: asks Paystack for the outcome."""
    _require_payments()
    payment = await db.find_one(Payment, {"reference": reference, "user_id": user.id})
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status == PaymentStatus.INITIALIZED.value:
        try:
            data = await paystack.verify_transaction(reference)
        except PaystackError as exc:
            raise _gateway_error(exc) from None
        await apply_paystack_result(db, payment, data, source="verify")
        await db.commit()
        await db.refresh(payment)
    return payment


async def list_topups(db: Session, user: User) -> list[Payment]:
    return await db.find(Payment, {"user_id": user.id}, sort=[("created_at", -1)], limit=100)


# --- Webhooks ----------------------------------------------------------------------------------------------


async def handle_webhook(db: Session, payload: dict[str, Any]) -> str:
    """Process one signature-verified Paystack event. Idempotent per event."""
    event = str(payload.get("event") or "")[:60]
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return "ignored_malformed"
    reference = str(data.get("reference") or "")[:100] or None
    ident = data.get("id") or reference or data.get("refund_reference") or data.get("transaction_reference")
    key = f"{event}:{ident}"[:200]
    inbox = PaymentEvent(provider="paystack", event_key=key, event_type=event or "unknown", reference=reference)
    db.add(inbox)
    try:
        await db.flush()
    except DuplicateKeyError:
        await db.rollback()
        return "duplicate"

    if event == "charge.success" and reference:
        payment = await db.find_one(Payment, {"reference": reference})
        outcome = await apply_paystack_result(db, payment, data, source="webhook") if payment else "unknown_reference"
    elif event.startswith("refund."):
        from app.services import refund_service

        outcome = await refund_service.handle_webhook_event(db, event, data)
    elif event.startswith("transfer.") and reference:
        payout = await db.find_one(Payout, {"reference": reference})
        outcome = await apply_transfer_result(db, payout, data) if payout else "unknown_reference"
    else:
        outcome = "ignored"
    inbox.outcome = outcome[:60]
    inbox.processed_at = utcnow()
    await db.commit()
    return outcome


# --- Payouts -----------------------------------------------------------------------------------------------


async def list_banks() -> list[dict[str, Any]]:
    _require_payments()
    try:
        banks = await paystack.list_banks(settings.BILLING_CURRENCY)
    except PaystackError as exc:
        raise _gateway_error(exc) from None
    return [{"name": b.get("name"), "code": b.get("code")} for b in banks if b.get("active", True) and b.get("code")]


async def get_payout_account(db: Session, user: User) -> PayoutAccount | None:
    return await db.find_one(PayoutAccount, {"user_id": user.id})


async def set_payout_account(db: Session, user: User, account_number: str, bank_code: str) -> PayoutAccount:
    _require_payments()
    try:
        resolved = await paystack.resolve_account(account_number, bank_code)
        name = str(resolved.get("account_name") or "")[:200]
        recipient = await paystack.create_recipient(
            name=name or user.email,
            account_number=account_number,
            bank_code=bank_code,
            currency=settings.BILLING_CURRENCY,
        )
    except PaystackError as exc:
        raise HTTPException(
            status_code=422 if exc.status and exc.status < 500 else 502, detail=f"Paystack: {exc}"
        ) from None
    details = recipient.get("details") or {}
    recipient_code = str(recipient.get("recipient_code") or "")
    if not recipient_code:
        raise HTTPException(status_code=502, detail="Paystack did not return a recipient code")
    fields = {
        "provider": "paystack",
        "recipient_code": recipient_code,
        "bank_code": bank_code,
        "bank_name": str(details.get("bank_name") or "")[:200] or None,
        "account_name": name or None,
        "account_last4": account_number[-4:],
        "currency": settings.BILLING_CURRENCY,
    }
    account = await get_payout_account(db, user)
    if account is None:
        account = PayoutAccount(id=uuid.uuid4(), user_id=user.id, **fields)
        db.add(account)
    else:
        for key, value in fields.items():
            setattr(account, key, value)
    audit_service.record(
        db,
        actor_id=user.id,
        action="payout.account_set",
        resource_type="payout_account",
        resource_id=account.id,
        details={"bank_code": bank_code, "account_last4": account.account_last4},
    )
    await db.commit()
    await db.refresh(account)
    return account


async def request_payout(db: Session, user: User, amount: Decimal) -> Payout:
    _require_payments()
    amount = money(amount)
    if amount != amount.quantize(Decimal("0.01")):
        raise HTTPException(status_code=422, detail="Amounts can have at most 2 decimal places")
    if amount < settings.PAYOUT_MIN_AMOUNT:
        raise HTTPException(
            status_code=422, detail=f"The minimum payout is {settings.PAYOUT_MIN_AMOUNT} {settings.BILLING_CURRENCY}"
        )
    account = await get_payout_account(db, user)
    if account is None:
        raise HTTPException(status_code=409, detail="Add a payout bank account first")
    wallet = await ledger_service.wallet_for_user(db, user.id)
    available = await ledger_service.balance(db, wallet.id)
    if amount > available:
        raise HTTPException(status_code=409, detail=f"Only {money(available)} {wallet.currency} is available")
    payout = Payout(
        id=uuid.uuid4(),
        user_id=user.id,
        wallet_id=wallet.id,
        payout_account_id=account.id,
        amount=amount,
        currency=settings.BILLING_CURRENCY,
        reference=f"am-po-{secrets.token_hex(12)}",
        status=PayoutStatus.REQUESTED.value,
    )
    db.add(payout)
    hold = await ledger_service.post(
        db,
        key=f"payout:{payout.reference}",
        type=TransactionType.PAYOUT,
        status=TransactionStatus.PENDING,
        amount=amount,
        from_wallet=wallet,
        reference=payout.reference,
        description=f"Payout to bank account ending {account.account_last4}",
    )
    # A concurrent request may have spent the same balance; the hold must not overdraw the wallet.
    if await ledger_service.balance(db, wallet.id) < 0:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Insufficient available balance")
    payout.transaction_id = hold.id
    audit_service.record(
        db,
        actor_id=user.id,
        action="payout.requested",
        resource_type="payout",
        resource_id=payout.id,
        details={"amount": str(amount), "reference": payout.reference},
    )
    await db.commit()
    if not settings.PAYOUTS_REQUIRE_APPROVAL:
        return await _send(db, payout, actor=None)
    await db.refresh(payout)
    return payout


async def list_payouts(db: Session, user: User | None, status: str | None = None) -> list[Payout]:
    filter: dict[str, Any] = {}
    if user is not None:
        filter["user_id"] = user.id
    if status:
        filter["status"] = status
    return await db.find(Payout, filter, sort=[("created_at", -1)], limit=200)


async def _hold(db: Session, payout: Payout) -> Transaction | None:
    return await db.get(Transaction, payout.transaction_id) if payout.transaction_id else None


async def _close(db: Session, payout: Payout, status: PayoutStatus, reason: str | None) -> bool:
    """Move an open payout to a final state, settling or releasing the held funds. Does not commit."""
    moved = await db.update_one(
        Payout,
        {"_id": payout.id, "status": {"$in": OPEN_PAYOUT}},
        {"$set": {"status": status.value, "failure_reason": reason, "completed_at": utcnow()}},
    )
    if not moved:
        return False
    hold = await _hold(db, payout)
    if hold is not None:
        if status == PayoutStatus.SUCCEEDED:
            await ledger_service.settle(db, hold)
        else:
            await ledger_service.fail(db, hold)
    await db.refresh(payout)
    return True


async def decide_payout(db: Session, payout_id: str, operator: User, approve: bool, reason: str | None) -> Payout:
    payout = await db.get(Payout, uuid.UUID(payout_id))
    if payout is None:
        raise HTTPException(status_code=404, detail="Payout not found")
    if payout.status != PayoutStatus.REQUESTED.value:
        raise HTTPException(status_code=409, detail=f"Payout is {payout.status}, not awaiting approval")
    payout.decided_by = operator.id
    payout.decided_at = utcnow()
    audit_service.record(
        db,
        actor_id=operator.id,
        action="payout.approved" if approve else "payout.rejected",
        resource_type="payout",
        resource_id=payout.id,
        details={"amount": str(payout.amount), "reason": reason} if reason else {"amount": str(payout.amount)},
    )
    if not approve:
        await _close(db, payout, PayoutStatus.REJECTED, reason or "Rejected by an operator")
        await db.commit()
        return payout
    await db.commit()
    return await _send(db, payout, actor=operator)


async def _send(db: Session, payout: Payout, actor: User | None) -> Payout:
    """Initiate the Paystack transfer. Commits."""
    account = await db.get(PayoutAccount, payout.payout_account_id)
    moved = await db.update_one(
        Payout,
        {"_id": payout.id, "status": PayoutStatus.REQUESTED.value},
        {"$set": {"status": PayoutStatus.PENDING.value}},
    )
    await db.commit()  # PENDING before calling Paystack: never send the same payout twice
    if not moved or account is None:
        await db.refresh(payout)
        return payout
    try:
        data = await paystack.initiate_transfer(
            amount=Decimal(payout.amount),
            recipient=account.recipient_code,
            reference=payout.reference,
            reason="AgentMesh provider payout",
        )
    except PaystackError as exc:
        if exc.uncertain:
            payout.failure_reason = f"Outcome unknown, will be reconciled: {exc}"[:300]
        else:
            await _close(db, payout, PayoutStatus.FAILED, f"Paystack refused the transfer: {exc}"[:300])
        await db.commit()
        await db.refresh(payout)
        return payout
    payout.transfer_code = str(data.get("transfer_code") or "")[:100] or None
    await apply_transfer_result(db, payout, data)
    await db.commit()
    await db.refresh(payout)
    return payout


async def apply_transfer_result(db: Session, payout: Payout, data: dict[str, Any]) -> str:
    """Apply a Paystack transfer record (initiate response, verify, or webhook). Does not commit."""
    status = str(data.get("status") or "")
    if payout.status not in OPEN_PAYOUT:
        return f"already_{payout.status.lower()}"
    if data.get("amount") is not None and from_subunits(data["amount"]) != Decimal(payout.amount):
        payout.failure_reason = "Paystack reported a different transfer amount; needs review"
        return "amount_mismatch"
    if status == "success":
        await _close(db, payout, PayoutStatus.SUCCEEDED, None)
        return "succeeded"
    if status in ("failed", "reversed"):
        final = PayoutStatus.REVERSED if status == "reversed" else PayoutStatus.FAILED
        await _close(db, payout, final, str(data.get("reason") or data.get("gateway_response") or status)[:300])
        return status
    if status == "otp":
        await db.update_one(
            Payout,
            {"_id": payout.id, "status": {"$in": OPEN_PAYOUT}},
            {
                "$set": {
                    "status": PayoutStatus.OTP_REQUIRED.value,
                    "failure_reason": "Paystack requires an OTP for transfers; disable transfer OTP for API use",
                }
            },
        )
        await db.refresh(payout)
        return "otp_required"
    return f"pending_{status or 'unknown'}"
