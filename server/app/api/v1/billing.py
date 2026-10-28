"""Prices on offer (public) and cost estimates. AgentMesh processes no payments: customers pay providers directly,
and estimates show both sides what usage comes to at the providers' published prices."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import Session, get_db
from app.core.dependencies import get_current_user, is_staff
from app.documents.billing import CostEstimate
from app.documents.user import UserRole
from app.schemas.billing import CostEstimateOut, CostSummaryOut, MarketOut
from app.services import cost_service, node_pricing_service

router = APIRouter()


def _scope(user, requested: str | None) -> str:
    default = {UserRole.customer: "customer", UserRole.provider: "provider"}.get(user.role, "network")
    chosen = requested or default
    allowed = {"customer", "provider", "network"} if is_staff(user) else {default}
    if chosen not in allowed:
        raise HTTPException(status_code=403, detail=f"Scope '{chosen}' is not available to this account")
    return chosen


@router.get("/market", response_model=MarketOut)
async def market(db: Session = Depends(get_db)):
    """Lowest and highest price of each unit, per currency, across machines that can take work now (providers set
    their own prices). Aggregates only; no machine is identified."""
    return await node_pricing_service.market(db)


@router.get("/estimates", response_model=list[CostEstimateOut])
async def estimates(
    deployment_id: uuid.UUID | None = None,
    scope: Literal["customer", "provider", "network"] | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Estimated cost of each window of use: of the caller's deployments (customers) or of work on the caller's
    machines (providers). Staff see all. Estimates, not payments."""
    match = await cost_service.scope_filter(db, current_user, _scope(current_user, scope))
    if deployment_id:
        match["deployment_id"] = deployment_id
    return await db.find(CostEstimate, match, sort=[("period_start", -1)], limit=limit)


@router.get("/estimates/summary", response_model=CostSummaryOut)
async def estimates_summary(
    days: int = Query(30, ge=1, le=365),
    scope: Literal["customer", "provider", "network"] | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Estimated totals per currency and per day over the last ``days``."""
    chosen = _scope(current_user, scope)
    match = await cost_service.scope_filter(db, current_user, chosen)
    return {"scope": chosen} | await cost_service.summary(db, match, days)
