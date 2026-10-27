"""Pricing (public) and rated charges (customers see what they paid, providers what they earned)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.core.database import Session, get_db
from app.core.dependencies import get_current_user, is_staff
from app.core.timeutil import utcnow
from app.documents.billing import Charge, PricingRule
from app.documents.user import UserRole
from app.schemas.billing import BillingSummary, ChargeOut, MarketOut, PricingOut, PricingRuleOut, RefundOut
from app.services import billing_service, ledger_service, node_pricing_service, refund_service

router = APIRouter()


@router.get("/pricing", response_model=PricingOut)
async def pricing(db: Session = Depends(get_db)):
    """The network price list in force: what machines without their own prices charge, and the default price
    limits for placement (null when none is set)."""
    upcoming = await db.find(PricingRule, {"effective_from": {"$gt": utcnow()}}, sort=[("effective_from", 1)])
    current = await billing_service.active_rule(db)
    return PricingOut(
        current=PricingRuleOut.model_validate(current) if current else None,
        upcoming=[PricingRuleOut.model_validate(r) for r in upcoming],
        currency=settings.BILLING_CURRENCY,
        min_prepaid_hours=settings.BILLING_MIN_PREPAID_HOURS,
        billing_interval_seconds=settings.BILLING_INTERVAL_SECONDS,
        default_platform_fee_rate=settings.DEFAULT_PLATFORM_FEE_RATE,
        max_platform_fee_rate=settings.MAX_PLATFORM_FEE_RATE,
    )


@router.get("/market", response_model=MarketOut)
async def market(db: Session = Depends(get_db)):
    """Lowest and highest price of each unit across machines that can take work now (providers set their own
    prices). Aggregates only; no machine is identified."""
    return await node_pricing_service.market(db)


@router.get("/summary", response_model=BillingSummary)
async def summary(
    days: int = Query(30, ge=1, le=365),
    scope: Literal["customer", "provider", "network"] | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Fee breakdown of rated charges: customers see what they paid (and how much of it was platform commission),
    providers what their nodes earned before and after commission, staff the whole network."""
    default = {UserRole.customer: "customer", UserRole.provider: "provider"}.get(current_user.role, "network")
    chosen = scope or default
    allowed = {"customer", "provider", "network"} if is_staff(current_user) else {default}
    if chosen not in allowed:
        raise HTTPException(status_code=403, detail=f"Scope '{chosen}' is not available to this account")
    result = await billing_service.summary(db, current_user, chosen, days)
    await db.commit()  # may have created the caller's wallet
    return result


@router.get("/charges", response_model=list[ChargeOut])
async def charges(
    deployment_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Charges against the caller's wallet (as customer) or credited to it (as provider). Staff see all."""
    filter: dict = {}
    if not is_staff(current_user):
        wallet = await ledger_service.wallet_for_user(db, current_user.id)
        filter["$or"] = [{"customer_wallet_id": wallet.id}, {"provider_wallet_id": wallet.id}]
    if deployment_id:
        filter["deployment_id"] = deployment_id
    rows = await db.find(Charge, filter, sort=[("created_at", -1)], limit=limit)
    await db.commit()
    return rows


@router.get("/refunds", response_model=list[RefundOut])
async def my_refunds(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Refunds issued to the caller (charge refunds to the wallet, and top-ups refunded to their card)."""
    return await refund_service.list_refunds(db, current_user)
