"""Prepaid credit with providers. Customers pay providers directly; AgentMesh verifies the payment (with the
provider's own gateway account, or the provider's confirmation) before priced service starts, and holds no money."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import Session, get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.ids import parse_uuid
from app.documents.credit import CreditBalance, CreditPayment
from app.documents.user import Customer, Provider, UserRole
from app.schemas.credit import CreditsOut, DecisionIn, PaymentOut, TopupIn
from app.services import credit_service, provider_service

router = APIRouter()


async def _names(db: Session, ids) -> dict:
    return {p.id: provider_service.display_name(p) for p in await db.find(Provider, {"_id": {"$in": list(ids)}})}


@router.get("", response_model=CreditsOut)
async def my_credit(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Customers: your credit with each provider and your payments. Providers: what your customers hold with you
    and the payments made to you (including manual ones waiting for your confirmation)."""
    if user.role == UserRole.customer:
        customer = await db.find_one(Customer, {"user_id": user.id})
        match = {"customer_id": customer.id if customer else None}
    elif user.role == UserRole.provider:
        provider = await db.find_one(Provider, {"user_id": user.id})
        match = {"provider_id": provider.id if provider else None}
    else:
        raise HTTPException(status_code=403, detail="Customers and providers only")
    balances = await db.find(CreditBalance, match, sort=[("updated_at", -1)])
    payments = await db.find(CreditPayment, match, sort=[("created_at", -1)], limit=200)
    names = await _names(db, {b.provider_id for b in balances})
    return {
        "balances": [
            {
                "provider_id": b.provider_id,
                "provider": names.get(b.provider_id, ""),
                "currency": b.currency,
                "balance": credit_service._dec(b.balance),
                "customer_ref": str(b.customer_id)[:8].upper() if user.role == UserRole.provider else None,
            }
            for b in balances
        ],
        "payments": payments,
    }


@router.post("/topups", response_model=PaymentOut, status_code=201)
async def start_topup(body: TopupIn, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.customer))):
    """Gateway: returns the provider's hosted checkout URL; you return to the dashboard, which verifies it.
    Manual: records your transfer for the provider to confirm."""
    return await credit_service.start_topup(
        db,
        user,
        provider_id=body.provider_id,
        amount=body.amount,
        currency=body.currency,
        method=body.method,
        gateway=body.gateway,
        reference=body.reference,
        note=body.note,
    )


async def _own_payment(db: Session, payment_id: str, user) -> CreditPayment:
    payment = await db.get(CreditPayment, parse_uuid(payment_id, "Payment"))
    owner = None
    if payment is not None:
        if user.role == UserRole.customer:
            owner = await db.find_one(Customer, {"user_id": user.id, "_id": payment.customer_id})
        elif user.role == UserRole.provider:
            owner = await db.find_one(Provider, {"user_id": user.id, "_id": payment.provider_id})
    if payment is None or owner is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.post("/topups/{payment_id}/verify", response_model=PaymentOut)
async def verify_topup(payment_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Ask the provider's gateway now whether this payment succeeded; credited once if it did."""
    payment = await _own_payment(db, payment_id, user)
    await credit_service.verify_payment(db, payment)
    await credit_service.after_verified(db, payment)
    await db.commit()
    await db.refresh(payment)
    return payment


@router.post("/topups/{payment_id}/decision", response_model=PaymentOut)
async def decide_topup(
    payment_id: str, body: DecisionIn, db: Session = Depends(get_db), user=Depends(require_roles(UserRole.provider))
):
    """Providers: confirm you received a manual payment (credits the customer) or reject it."""
    payment = await _own_payment(db, payment_id, user)
    await credit_service.decide_manual(db, payment, user, body.accept, body.reason)
    await credit_service.after_verified(db, payment)
    await db.commit()
    await db.refresh(payment)
    return payment
