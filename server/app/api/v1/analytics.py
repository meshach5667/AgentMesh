"""Revenue analytics for the customer, provider and operator dashboards."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import Session, get_db
from app.core.dependencies import get_current_user, is_staff
from app.documents.user import UserRole
from app.services import analytics_service

router = APIRouter()


@router.get("/revenue")
async def revenue(
    days: int = Query(30, ge=1, le=365),
    scope: Literal["customer", "provider", "network"] | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Daily charges and refunds with totals: customers see their spending, providers their earnings, staff the
    network's compute revenue (plus payments, payouts and sponsorship revenue as a separate stream)."""
    default = {UserRole.customer: "customer", UserRole.provider: "provider"}.get(current_user.role, "network")
    chosen = scope or default
    allowed = {"customer", "provider", "network"} if is_staff(current_user) else {default}
    if chosen not in allowed:
        raise HTTPException(status_code=403, detail=f"Scope '{chosen}' is not available to this account")
    result = await analytics_service.revenue(db, current_user, chosen, days)
    await db.commit()  # may have created the caller's wallet
    return result
