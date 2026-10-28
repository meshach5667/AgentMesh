"""Prepaid credit with providers: verified payments add to it, usage draws it down, and priced service needs it.

Payment is verified before service, in one of two ways the provider chooses:

* gateway: the customer pays through the provider's own Paystack, Flutterwave or Stripe account; AgentMesh asks that
  gateway (with the provider's key) whether the payment succeeded, and credits it only when the gateway reports
  success for exactly the amount and currency asked. Checked when the customer returns from checkout and again in the
  background until it settles.
* manual: the customer pays by the provider's published method and records it; the provider confirms receipt.

Credit changes are append-only CreditEntry rows with unique keys, applied in the same transaction as the balance, so
a payment is credited and a usage window is drawn down exactly once. Usage is drawn down from cost estimates (every
COST_ESTIMATE_INTERVAL_SECONDS), so a balance can go below zero by at most about one interval before the deployment
is paused; the gateway also refuses requests once the balance is used up.
"""

import logging
import secrets
import uuid
from datetime import timedelta
from decimal import Decimal

from bson import Decimal128
from fastapi import HTTPException

from app.core import crypto
from app.core.config import settings
from app.core.database import Session, session_scope
from app.core.timeutil import utcnow
from app.documents.credit import (
    CreditBalance,
    CreditEntry,
    CreditPayment,
    PaymentMethod,
    PaymentState,
    ProviderGateway,
)
from app.documents.user import Customer, Provider, User
from app.services import audit_service, gateways

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")


def _dec(v) -> Decimal:
    return v.to_decimal() if hasattr(v, "to_decimal") else Decimal(str(v or 0))


# --- Balances ----------------------------------------------------------------------------------------------


async def balance(db: Session, customer_id, provider_id, currency: str) -> Decimal:
    row = await db.find_one(
        CreditBalance, {"customer_id": customer_id, "provider_id": provider_id, "currency": currency}
    )
    if row is None:
        return Decimal(0)
    await db.refresh(row)  # balances change by atomic $inc: never trust a copy loaded earlier in this session
    return _dec(row.balance)


async def balances_for(db: Session, customer_id) -> dict[tuple[uuid.UUID, str], Decimal]:
    rows = await db.find(CreditBalance, {"customer_id": customer_id})
    for r in rows:
        await db.refresh(r)
    return {(r.provider_id, r.currency): _dec(r.balance) for r in rows}


def credit_needed(hourly: Decimal) -> Decimal:
    """Credit a customer must hold with a provider to be placed on one of its priced machines."""
    return (hourly * Decimal(str(settings.CREDIT_MIN_PREPAID_HOURS))).quantize(CENT)


def covers(have: Decimal, hourly: Decimal) -> bool:
    return have > 0 and have >= credit_needed(hourly)


async def post(
    db: Session,
    *,
    customer_id,
    provider_id,
    currency: str,
    amount: Decimal,
    kind: str,
    key: str,
    **refs,
) -> bool:
    """Apply one change to a balance, once (False if ``key`` was already applied). Does not commit."""
    if await db.find_one(CreditEntry, {"key": key}):
        return False
    db.add(
        CreditEntry(
            customer_id=customer_id,
            provider_id=provider_id,
            currency=currency,
            amount=amount,
            kind=kind,
            key=key,
            **refs,
        )
    )
    await db.flush()  # the unique key rejects a concurrent duplicate here
    owner = {"customer_id": customer_id, "provider_id": provider_id, "currency": currency}
    if not await db.find_one(CreditBalance, owner):
        db.add(CreditBalance(**owner))
        await db.flush()
    await db.update_one(
        CreditBalance, owner, {"$inc": {"balance": Decimal128(str(amount))}, "$set": {"updated_at": utcnow()}}
    )
    return True


# --- Provider gateway accounts -----------------------------------------------------------------------------


def _context(provider_id, gateway: str) -> str:
    return f"gateway:{provider_id}:{gateway}"


async def connect_gateway(db: Session, provider: Provider, gateway: str, secret: str, actor: User) -> ProviderGateway:
    secret = secret.strip()
    mode = gateways.key_mode(gateway, secret)
    if mode is None:
        raise HTTPException(status_code=422, detail=f"That is not a {gateway} secret key")
    try:
        await gateways.check_key(gateway, secret)
    except gateways.GatewayError as exc:
        raise HTTPException(status_code=422, detail=f"The key was refused: {exc}") from None
    row = await db.find_one(ProviderGateway, {"provider_id": provider.id, "gateway": gateway})
    now = utcnow()
    sealed = crypto.encrypt(secret.encode(), _context(provider.id, gateway))
    if row is None:
        row = ProviderGateway(
            provider_id=provider.id, gateway=gateway, secret_encrypted=sealed, key_hint=secret[-4:], mode=mode
        )
        db.add(row)
    else:
        row.secret_encrypted, row.key_hint, row.mode, row.updated_at = sealed, secret[-4:], mode, now
    row.verified_at = now
    audit_service.record(
        db,
        actor_id=actor.id,
        action="provider.gateway_connected",
        resource_type="provider",
        resource_id=provider.id,
        details={"gateway": gateway, "mode": mode, "key_hint": row.key_hint},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def disconnect_gateway(db: Session, provider: Provider, gateway: str, actor: User) -> None:
    await db.delete_many(ProviderGateway, {"provider_id": provider.id, "gateway": gateway})
    audit_service.record(
        db,
        actor_id=actor.id,
        action="provider.gateway_disconnected",
        resource_type="provider",
        resource_id=provider.id,
        details={"gateway": gateway},
    )
    await db.commit()


async def _secret(db: Session, provider_id, gateway: str) -> str:
    row = await db.find_one(ProviderGateway, {"provider_id": provider_id, "gateway": gateway})
    if row is None:
        raise HTTPException(status_code=409, detail=f"This provider does not accept {gateway} payments")
    try:
        return crypto.decrypt(row.secret_encrypted, _context(provider_id, gateway)).decode()
    except ValueError:
        raise HTTPException(status_code=409, detail="The provider must reconnect this gateway") from None


async def connected_gateways(db: Session, provider_id) -> list[ProviderGateway]:
    return await db.find(ProviderGateway, {"provider_id": provider_id}, sort=[("gateway", 1)])


# --- Payments ----------------------------------------------------------------------------------------------


async def _customer(db: Session, user: User) -> Customer:
    customer = await db.find_one(Customer, {"user_id": user.id})
    if customer is None:
        raise HTTPException(status_code=403, detail="Customer account required")
    return customer


async def start_topup(
    db: Session,
    user: User,
    *,
    provider_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    method: str,
    gateway: str | None,
    reference: str | None,
    note: str | None,
) -> CreditPayment:
    customer = await _customer(db, user)
    provider = await db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    if method == PaymentMethod.GATEWAY.value:
        if gateway not in gateways.GATEWAYS:
            raise HTTPException(status_code=422, detail="Choose a gateway: paystack, flutterwave or stripe")
        secret = await _secret(db, provider.id, gateway)
        payment = CreditPayment(
            customer_id=customer.id,
            provider_id=provider.id,
            method=method,
            gateway=gateway,
            amount=amount,
            currency=currency,
            reference=f"am-cr-{secrets.token_hex(12)}",
            note=note,
        )
        return_url = f"{settings.FRONTEND_URL.rstrip('/')}/customer/credits?payment={payment.id}"
        try:
            checkout = await gateways.start_checkout(
                gateway,
                secret,
                reference=payment.reference,
                amount=amount,
                currency=currency,
                email=user.email,
                return_url=return_url,
            )
        except gateways.GatewayError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from None
        payment.checkout_url, payment.gateway_ref = checkout.url, checkout.gateway_ref
    else:
        from app.services.provider_service import has_arrangement, payment_of

        if not has_arrangement(payment_of(provider)):
            raise HTTPException(status_code=409, detail="This provider has not published how to pay them by hand")
        if not reference:
            raise HTTPException(
                status_code=422, detail="Give the reference of your transfer so the provider can find it"
            )
        payment = CreditPayment(
            customer_id=customer.id,
            provider_id=provider.id,
            method=PaymentMethod.MANUAL.value,
            amount=amount,
            currency=currency,
            reference=reference,
            note=note,
        )
    db.add(payment)
    audit_service.record(
        db,
        actor_id=user.id,
        action="credit.payment_started",
        resource_type="credit_payment",
        resource_id=payment.id,
        details={"method": payment.method, "gateway": gateway, "amount": str(amount), "currency": currency},
    )
    try:
        await db.commit()
    except Exception as exc:  # duplicate manual reference for this provider
        await db.rollback()
        if "uq_credit_payments_reference" in str(exc):
            raise HTTPException(status_code=409, detail="A payment with this reference was already recorded") from None
        raise
    await db.refresh(payment)
    return payment


async def _credit(db: Session, payment: CreditPayment, actor_id) -> None:
    """Mark a payment VERIFIED and credit it, once. Does not commit."""
    if not await db.update_one(
        CreditPayment,
        {"_id": payment.id, "state": PaymentState.PENDING.value},
        {"$set": {"state": PaymentState.VERIFIED.value, "verified_at": utcnow(), "decided_by": actor_id}},
    ):
        return
    payment.state = PaymentState.VERIFIED.value
    await post(
        db,
        customer_id=payment.customer_id,
        provider_id=payment.provider_id,
        currency=payment.currency,
        amount=_dec(payment.amount),
        kind="payment",
        key=f"payment:{payment.id}",
        payment_id=payment.id,
    )
    audit_service.record(
        db,
        actor_id=actor_id,
        action="credit.payment_verified",
        resource_type="credit_payment",
        resource_id=payment.id,
        details={"method": payment.method, "amount": str(payment.amount), "currency": payment.currency},
    )


async def verify_payment(db: Session, payment: CreditPayment) -> CreditPayment:
    """Ask the provider's gateway about a pending gateway payment and settle it. Does not commit."""
    if payment.method != PaymentMethod.GATEWAY.value or payment.state != PaymentState.PENDING.value:
        return payment
    secret = await _secret(db, payment.provider_id, str(payment.gateway))
    try:
        result = await gateways.verify(
            str(payment.gateway), secret, reference=payment.reference, gateway_ref=payment.gateway_ref
        )
    except gateways.GatewayError as exc:
        logger.warning("Verifying credit payment %s failed: %s", payment.id, exc)
        payment.last_checked_at = utcnow()
        return payment
    payment.gateway_status, payment.last_checked_at = result.status, utcnow()
    if result.paid:
        if result.amount == _dec(payment.amount).quantize(CENT) and result.currency == payment.currency:
            await _credit(db, payment, None)
        else:
            payment.state = PaymentState.REVIEW.value
            payment.reason = (
                f"Gateway reported {result.amount} {result.currency}, expected {payment.amount} {payment.currency}"
            )
    elif result.failed:
        payment.state = PaymentState.FAILED.value
        payment.reason = f"Gateway status: {result.status}"
    return payment


async def decide_manual(db: Session, payment: CreditPayment, provider_user: User, accept: bool, reason: str | None):
    provider = await db.find_one(Provider, {"user_id": provider_user.id})
    if provider is None or payment.provider_id != provider.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.method != PaymentMethod.MANUAL.value:
        raise HTTPException(status_code=409, detail="Gateway payments are verified with the gateway, not by hand")
    if payment.state != PaymentState.PENDING.value:
        raise HTTPException(status_code=409, detail=f"Payment is already {payment.state}")
    if accept:
        await _credit(db, payment, provider_user.id)
    else:
        if await db.update_one(
            CreditPayment,
            {"_id": payment.id, "state": PaymentState.PENDING.value},
            {"$set": {"state": PaymentState.REJECTED.value, "reason": reason, "decided_by": provider_user.id}},
        ):
            payment.state, payment.reason = PaymentState.REJECTED.value, reason
            audit_service.record(
                db,
                actor_id=provider_user.id,
                action="credit.payment_rejected",
                resource_type="credit_payment",
                resource_id=payment.id,
                details={"reason": reason},
            )
    return payment


async def resume_paused(db: Session, customer_id) -> int:
    """Place deployments paused for lack of credit again, now that this customer topped up. Does not commit."""
    from app.documents.deployment import Deployment
    from app.documents.deployment import DeploymentStatus as S
    from app.services import placement_service

    placed = 0
    for dep in await db.find(
        Deployment, {"customer_id": customer_id, "status": S.NEEDS_ATTENTION.value, "error_code": "CREDIT_EXHAUSTED"}
    ):
        if await placement_service.retry_placement(db, dep, actor="system"):
            placed += 1
    return placed


async def after_verified(db: Session, payment: CreditPayment) -> None:
    if payment.state == PaymentState.VERIFIED.value:
        await resume_paused(db, payment.customer_id)


async def run_pending(now=None) -> int:
    """Re-check pending gateway payments until they settle; give up after PAYMENT_VERIFY_WINDOW_HOURS."""
    now = now or utcnow()
    settled = 0
    async with session_scope() as db:
        ids = [
            p.id
            for p in await db.find(
                CreditPayment,
                {
                    "state": PaymentState.PENDING.value,
                    "method": PaymentMethod.GATEWAY.value,
                    "created_at": {"$lt": now - timedelta(seconds=30)},
                },
                limit=200,
            )
        ]
    for pid in ids:
        async with session_scope() as db:
            payment = await db.get(CreditPayment, pid)
            if payment is None:
                continue
            try:
                if now - payment.created_at > timedelta(hours=settings.PAYMENT_VERIFY_WINDOW_HOURS):
                    await db.update_one(
                        CreditPayment,
                        {"_id": pid, "state": PaymentState.PENDING.value},
                        {"$set": {"state": PaymentState.FAILED.value, "reason": "Not completed in time"}},
                    )
                else:
                    await verify_payment(db, payment)
                    await after_verified(db, payment)
                await db.commit()
                settled += payment.state != PaymentState.PENDING.value
            except Exception:  # noqa: BLE001 - one payment must not block the rest
                await db.rollback()
                logger.exception("Checking credit payment %s failed", pid)
    return settled
