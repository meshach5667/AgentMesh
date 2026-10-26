"""Operator endpoints. Every route requires the operator or admin role."""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.transactions import ledger_filter
from app.core.database import Session, get_db
from app.core.dependencies import require_roles
from app.documents.billing import Payment, PaymentStatus
from app.documents.model import Model
from app.documents.transaction import Transaction
from app.documents.user import User, UserRole
from app.schemas.billing import (
    AdminTopupOut,
    CommissionChange,
    PaymentOut,
    PayoutDecision,
    PayoutOut,
    PricingRuleCreate,
    PricingRuleOut,
    RefundCreate,
    RefundOut,
)
from app.schemas.deployment import DeploymentOut
from app.schemas.model import ModelOut
from app.schemas.node import NodeOut
from app.schemas.transaction import TransactionResponse, TransactionStatusEnum, TransactionTypeEnum
from app.services import (
    audit_service,
    billing_service,
    node_service,
    payments_service,
    reconciliation_service,
    refund_service,
    reporting_service,
    sponsorship_service,
)
from app.services.catalog_service import load_artifacts
from app.services.sponsorship_service import AdSettingsUpdate, CampaignIn, StatusChange

logger = logging.getLogger(__name__)
router = APIRouter()
staff_only = require_roles(UserRole.operator, UserRole.admin)


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str | None
    resource_type: str | None
    resource_id: str | None
    details: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime | None


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def audit_logs(
    action: str | None = Query(None, max_length=100),
    resource_type: str | None = Query(None, max_length=100),
    resource_id: str | None = Query(None, max_length=100),
    actor_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _staff=Depends(staff_only),
):
    return await audit_service.search(
        db, action=action, resource_type=resource_type, resource_id=resource_id, actor_id=actor_id, limit=limit
    )


class AdminNodeOut(NodeOut):
    owner_email: str | None = None


class AdminDeploymentOut(DeploymentOut):
    customer_email: str | None = None


@router.get("/overview")
async def overview(db: Session = Depends(get_db), _staff=Depends(staff_only)):
    """Network-wide counts: nodes and deployments by status, catalog, last-24h usage, and ledger totals."""
    return await reporting_service.operator_overview(db)


@router.get("/nodes", response_model=list[AdminNodeOut])
async def all_nodes(
    status: str | None = Query(None, max_length=20),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _staff=Depends(staff_only),
):
    rows = await reporting_service.list_nodes_with_owner(db, status, limit)
    return [AdminNodeOut(**NodeOut.model_validate(n).model_dump(), owner_email=email) for n, email in rows]


@router.get("/anomalies")
async def anomalies(
    hours: int = Query(24, ge=1, le=24 * 30), db: Session = Depends(get_db), _staff=Depends(staff_only)
):
    """Provider signals worth investigating (token over-claims, failure rates), from metering metadata only."""
    return await reporting_service.provider_anomalies(db, hours)


class QuarantineIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/nodes/{node_id}/quarantine", response_model=NodeOut)
async def quarantine_node(
    node_id: str, body: QuarantineIn, db: Session = Depends(get_db), user: User = Depends(staff_only)
):
    """Cut a node off immediately pending investigation: no authentication, no tunnel, no work. Reversible."""
    return await node_service.quarantine_node(db, node_id, user, body.reason)


@router.post("/nodes/{node_id}/release", response_model=NodeOut)
async def release_node(node_id: str, db: Session = Depends(get_db), user: User = Depends(staff_only)):
    return await node_service.release_node(db, node_id, user)


@router.get("/deployments", response_model=list[AdminDeploymentOut])
async def all_deployments(
    status: str | None = Query(None, max_length=20),
    node_id: uuid.UUID | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _staff=Depends(staff_only),
):
    rows = await reporting_service.list_deployments_with_owner(db, status, node_id, limit)
    return [
        AdminDeploymentOut(**DeploymentOut.model_validate(d).model_dump(exclude={"openai_base_url"}), customer_email=e)
        for d, e in rows
    ]


@router.get("/models", response_model=list[ModelOut])
async def all_models(db: Session = Depends(get_db), _staff=Depends(staff_only)):
    """The whole catalog, including unapproved models and disabled artifacts."""
    models = await db.find(Model, sort=[("name", 1), ("_id", 1)])
    await load_artifacts(db, models)
    return models


@router.get("/transactions", response_model=list[TransactionResponse])
async def ledger(
    type: list[TransactionTypeEnum] | None = Query(None),
    status: TransactionStatusEnum | None = None,
    reference: str | None = Query(None, max_length=100),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=100_000),
    db: Session = Depends(get_db),
    _staff=Depends(staff_only),
):
    filter = ledger_filter(type, status, None, None)
    if reference:
        filter["reference"] = reference
    return await db.find(Transaction, filter, sort=[("created_at", -1), ("_id", -1)], skip=offset, limit=limit)


# --- Refunds ---


@router.get("/topups", response_model=list[AdminTopupOut])
async def topups(
    status: str | None = Query(None, max_length=20),
    email: str | None = Query(None, max_length=254),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _staff=Depends(staff_only),
):
    """Customer top-ups, newest first, with how much of each can still be refunded."""
    filter: dict = {"status": status} if status else {}
    if email:
        user = await db.find_one(User, {"email": email.strip()})
        filter["user_id"] = user.id if user else None
    payments = await db.find(Payment, filter, sort=[("created_at", -1)], limit=limit)
    emails = {u.id: u.email for u in await db.find(User, {"_id": {"$in": [p.user_id for p in payments]}})}
    return [
        AdminTopupOut(
            **PaymentOut.model_validate(p).model_dump(),
            user_email=emails.get(p.user_id),
            refundable=await refund_service.refundable(db, p)
            if p.status == PaymentStatus.SUCCEEDED.value
            else Decimal(0),
        )
        for p in payments
    ]


@router.get("/refunds", response_model=list[RefundOut])
async def refunds(
    status: str | None = Query(None, max_length=20), db: Session = Depends(get_db), _staff=Depends(staff_only)
):
    return await refund_service.list_refunds(db, None, status)


@router.post("/refunds/charges/{charge_id}", response_model=RefundOut, status_code=201)
async def refund_charge(charge_id: str, req: RefundCreate, db: Session = Depends(get_db), staff=Depends(staff_only)):
    """Credit (part of) a compute charge back to the customer's wallet; the provider's share and the commission
    are reversed in the same proportions."""
    return await refund_service.refund_charge(db, charge_id, req.amount, req.reason, staff)


@router.post("/refunds/topups/{payment_id}", response_model=RefundOut, status_code=201)
async def refund_topup(payment_id: str, req: RefundCreate, db: Session = Depends(get_db), staff=Depends(staff_only)):
    """Send unspent wallet funds back to the customer's card through Paystack."""
    return await refund_service.refund_topup(db, payment_id, req.amount, req.reason, staff)


# --- Sponsored placements ---


async def _ad_settings_view(db: Session) -> dict:
    current = await sponsorship_service.get_settings(db)
    return {
        "enabled": current.enabled,
        "placements": [
            {"key": key, "label": label, **current.placements[key]}
            for key, label in sponsorship_service.PLACEMENTS.items()
        ],
        "updated_at": current.updated_at,
    }


@router.get("/ads/settings")
async def ad_settings(db: Session = Depends(get_db), _staff=Depends(staff_only)):
    return await _ad_settings_view(db)


@router.put("/ads/settings")
async def update_ad_settings(req: AdSettingsUpdate, db: Session = Depends(get_db), staff=Depends(staff_only)):
    """Turn advertising on or off as a whole, and each placement, with how many items it shows."""
    await sponsorship_service.update_settings(db, req, staff)
    return await _ad_settings_view(db)


@router.get("/ads/campaigns")
async def campaigns(
    status: str | None = Query(None, max_length=20), db: Session = Depends(get_db), _staff=Depends(staff_only)
):
    rows = await sponsorship_service.list_campaigns(db, status)
    window = await sponsorship_service.stats(db, [c.id for c in rows], sponsorship_service.since_days(30))
    return [sponsorship_service.campaign_view(c, window.get(c.id)) for c in rows]


@router.post("/ads/campaigns", status_code=201)
async def create_campaign(req: CampaignIn, db: Session = Depends(get_db), staff=Depends(staff_only)):
    """New campaigns start as drafts; activate them when ready."""
    return sponsorship_service.campaign_view(await sponsorship_service.create_campaign(db, req, staff))


@router.put("/ads/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, req: CampaignIn, db: Session = Depends(get_db), staff=Depends(staff_only)):
    return sponsorship_service.campaign_view(await sponsorship_service.update_campaign(db, campaign_id, req, staff))


@router.post("/ads/campaigns/{campaign_id}/status")
async def campaign_status(
    campaign_id: str, req: StatusChange, db: Session = Depends(get_db), staff=Depends(staff_only)
):
    """draft -> active, active <-> paused, any -> ended (final)."""
    return sponsorship_service.campaign_view(await sponsorship_service.set_status(db, campaign_id, req.status, staff))


@router.get("/pricing", response_model=list[PricingRuleOut])
async def pricing_versions(db: Session = Depends(get_db), _staff=Depends(staff_only)):
    return await billing_service.list_rules(db)


@router.post("/pricing", response_model=PricingRuleOut, status_code=201)
async def create_pricing_version(req: PricingRuleCreate, db: Session = Depends(get_db), staff=Depends(staff_only)):
    """Publish a new, immutable pricing version. It applies from ``effective_from`` (now or later); usage
    before that keeps the price it was rated at."""
    return await billing_service.create_rule(db, req.model_dump(), staff)


@router.post("/commission", response_model=PricingRuleOut, status_code=201)
async def change_commission(req: CommissionChange, db: Session = Depends(get_db), staff=Depends(staff_only)):
    """Change the platform commission without changing prices: publishes a new version with the prices in force.
    Charges already rated keep the rate they were split at."""
    return await billing_service.change_commission(db, req.platform_fee_rate, req.effective_from, req.notes, staff)


@router.get("/payouts", response_model=list[PayoutOut])
async def payouts(
    status: str | None = Query(None, max_length=20), db: Session = Depends(get_db), _staff=Depends(staff_only)
):
    return await payments_service.list_payouts(db, None, status)


@router.post("/payouts/{payout_id}/approve", response_model=PayoutOut)
async def approve_payout(payout_id: uuid.UUID, db: Session = Depends(get_db), staff=Depends(staff_only)):
    return await payments_service.decide_payout(db, str(payout_id), staff, True, None)


@router.post("/payouts/{payout_id}/reject", response_model=PayoutOut)
async def reject_payout(
    payout_id: uuid.UUID, req: PayoutDecision, db: Session = Depends(get_db), staff=Depends(staff_only)
):
    return await payments_service.decide_payout(db, str(payout_id), staff, False, req.reason)


@router.get("/reconciliation")
async def reconciliation_report(db: Session = Depends(get_db), _staff=Depends(staff_only)):
    """Ledger invariants and open payment items. Read-only."""
    return await reconciliation_service.report(db)


@router.post("/reconciliation/run")
async def reconciliation_run(staff=Depends(staff_only)):
    """Ask Paystack about stale top-ups and payouts and apply the answers (also runs in the background)."""
    result = await reconciliation_service.run()
    logger.info("Reconciliation run by %s: %s", staff.id, result)
    return result
