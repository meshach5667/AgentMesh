"""Sponsored placements: clearly labelled, optional, operator-managed promotions of AI tools, GPU hardware and
infrastructure providers.

* Off by default. An operator enables advertising as a whole and each placement (slot) separately, and sets how
  many items a slot shows. Slots exist where the dashboard has room for them (PLACEMENTS); nothing else is
  configurable in code.
* A campaign is served only while it is active, inside its dates, assigned to the slot, and under its budget.
  Among eligible campaigns the choice is random, weighted by ``weight``.
* Measurement: each served item carries a signed view token. The dashboard reports an impression when the item
  is shown; clicks go through /sponsored/{id}/click, which counts them and redirects to the campaign's own URL
  (never a URL from the request). Each token is counted at most once per kind, so reloading or replaying a request
  does not inflate numbers. No cookies, no third-party scripts, nothing about the viewer is stored.
* Revenue is computed from the counts: CPM per 1000 impressions, CPC per click, or a flat fee, and reported as a
  separate stream from compute commission.
"""

import base64
import hashlib
import hmac
import random
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.database import Session
from app.core.ids import parse_uuid
from app.core.keys import derive_key
from app.core.timeutil import utcnow
from app.documents.sponsorship import (
    AdSettings,
    CampaignStatus,
    PricingModel,
    SponsorCampaign,
    SponsorCategory,
    SponsorStat,
    SponsorView,
)
from app.documents.user import User
from app.services import audit_service
from app.services.ledger_service import money

SETTINGS_ID = uuid.uuid5(uuid.NAMESPACE_URL, "agentmesh:ad-settings")
TOKEN_TTL_SECONDS = 3600
MAX_ITEMS_PER_PLACEMENT = 3

# Slots the dashboard renders. Operators enable them and set how many items each shows.
PLACEMENTS: dict[str, str] = {
    "landing": "Landing page, below pricing (public)",
    "docs": "Documentation sidebar (public)",
    "customer_dashboard": "Customer overview",
    "provider_dashboard": "Provider overview",
}


# --- Settings ----------------------------------------------------------------------------------------------


def _default_placements() -> dict[str, dict[str, Any]]:
    return {key: {"enabled": False, "max_items": 1} for key in PLACEMENTS}


async def get_settings(db: Session) -> AdSettings:
    stored = await db.get(AdSettings, SETTINGS_ID)
    if stored is None:
        return AdSettings(id=SETTINGS_ID, enabled=False, placements=_default_placements())
    # Slots added in later versions start disabled.
    stored.placements = _default_placements() | {k: v for k, v in (stored.placements or {}).items() if k in PLACEMENTS}
    return stored


class PlacementConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    max_items: int = Field(1, ge=1, le=MAX_ITEMS_PER_PLACEMENT)


class AdSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    placements: dict[str, PlacementConfig] | None = None

    @field_validator("placements")
    @classmethod
    def _known(cls, value: dict[str, PlacementConfig] | None) -> dict[str, PlacementConfig] | None:
        unknown = set(value or {}) - set(PLACEMENTS)
        if unknown:
            raise ValueError(f"Unknown placements: {', '.join(sorted(unknown))}")
        return value


async def update_settings(db: Session, change: AdSettingsUpdate, actor: User) -> AdSettings:
    current = await get_settings(db)
    if change.enabled is not None:
        current.enabled = change.enabled
    if change.placements:
        current.placements = current.placements | {k: v.model_dump() for k, v in change.placements.items()}
    current.updated_by = actor.id
    current.updated_at = utcnow()
    if await db.get(AdSettings, SETTINGS_ID) is None:
        db.add(current)
    audit_service.record(
        db,
        actor_id=actor.id,
        action="ads.settings_updated",
        resource_type="ad_settings",
        resource_id=SETTINGS_ID,
        details={"enabled": current.enabled, "placements": current.placements},
    )
    await db.commit()
    return current


# --- Campaigns ---------------------------------------------------------------------------------------------


def _https_url(value: str | None, field: str) -> str | None:
    if value is None or value == "":
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or any(c.isspace() for c in value):
        raise ValueError(f"{field} must be an https:// URL")
    return value


class CampaignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    sponsor: str = Field(min_length=2, max_length=60)
    category: SponsorCategory
    headline: str = Field(min_length=3, max_length=80)
    body: str | None = Field(None, max_length=200)
    cta_label: str = Field("Learn more", min_length=2, max_length=24)
    target_url: str = Field(max_length=500)
    image_url: str | None = Field(None, max_length=500)
    placements: list[str] = Field(min_length=1, max_length=len(PLACEMENTS))
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    weight: int = Field(1, ge=1, le=100)
    pricing_model: PricingModel = PricingModel.CPM
    rate: Decimal = Field(Decimal(0), ge=0, le=Decimal("100000000"), max_digits=18, decimal_places=8)
    budget: Decimal | None = Field(None, gt=0, le=Decimal("100000000000"), max_digits=18, decimal_places=8)

    @field_validator("target_url")
    @classmethod
    def _target(cls, v: str) -> str:
        return _https_url(v, "target_url") or ""

    @field_validator("image_url")
    @classmethod
    def _image(cls, v: str | None) -> str | None:
        return _https_url(v, "image_url")

    @field_validator("placements")
    @classmethod
    def _placements(cls, v: list[str]) -> list[str]:
        unknown = set(v) - set(PLACEMENTS)
        if unknown:
            raise ValueError(f"Unknown placements: {', '.join(sorted(unknown))}")
        return sorted(set(v))

    @field_validator("starts_at", "ends_at")
    @classmethod
    def _naive_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is not None:
            v = v.astimezone(UTC).replace(tzinfo=None)
        return v

    @model_validator(mode="after")
    def _dates(self) -> "CampaignIn":
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: CampaignStatus


async def create_campaign(db: Session, data: CampaignIn, actor: User) -> SponsorCampaign:
    campaign = SponsorCampaign(**data.model_dump(mode="python"), created_by=actor.id)
    campaign.category = data.category.value
    campaign.pricing_model = data.pricing_model.value
    db.add(campaign)
    audit_service.record(
        db,
        actor_id=actor.id,
        action="ads.campaign_created",
        resource_type="sponsor_campaign",
        resource_id=campaign.id,
        details={"sponsor": campaign.sponsor, "placements": campaign.placements, "pricing": campaign.pricing_model},
    )
    await db.commit()
    return campaign


async def get_campaign(db: Session, campaign_id: str) -> SponsorCampaign:
    campaign = await db.get(SponsorCampaign, parse_uuid(campaign_id, "Campaign"))
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


async def update_campaign(db: Session, campaign_id: str, data: CampaignIn, actor: User) -> SponsorCampaign:
    campaign = await get_campaign(db, campaign_id)
    if campaign.status == CampaignStatus.ENDED.value:
        raise HTTPException(status_code=409, detail="Ended campaigns cannot be changed")
    for key, value in data.model_dump(mode="python").items():
        setattr(campaign, key, getattr(value, "value", value))
    campaign.updated_at = utcnow()
    audit_service.record(
        db, actor_id=actor.id, action="ads.campaign_updated", resource_type="sponsor_campaign", resource_id=campaign.id
    )
    await db.commit()
    return campaign


ALLOWED_STATUS = {
    CampaignStatus.DRAFT.value: {CampaignStatus.ACTIVE.value, CampaignStatus.ENDED.value},
    CampaignStatus.ACTIVE.value: {CampaignStatus.PAUSED.value, CampaignStatus.ENDED.value},
    CampaignStatus.PAUSED.value: {CampaignStatus.ACTIVE.value, CampaignStatus.ENDED.value},
    CampaignStatus.ENDED.value: set(),
}


async def set_status(db: Session, campaign_id: str, status: CampaignStatus, actor: User) -> SponsorCampaign:
    campaign = await get_campaign(db, campaign_id)
    if status.value == campaign.status:
        return campaign
    if status.value not in ALLOWED_STATUS[campaign.status]:
        raise HTTPException(status_code=409, detail=f"A {campaign.status} campaign cannot become {status.value}")
    previous, campaign.status, campaign.updated_at = campaign.status, status.value, utcnow()
    audit_service.record(
        db,
        actor_id=actor.id,
        action="ads.campaign_status",
        resource_type="sponsor_campaign",
        resource_id=campaign.id,
        details={"from": previous, "to": status.value},
    )
    await db.commit()
    return campaign


def earned(campaign: SponsorCampaign) -> Decimal:
    """Revenue earned so far from the campaign's counted impressions and clicks (or its flat fee)."""
    rate = money(campaign.rate or 0)
    if campaign.pricing_model == PricingModel.CPC.value:
        return money(rate * campaign.clicks)
    if campaign.pricing_model == PricingModel.FLAT.value:
        return rate
    return money(rate * campaign.impressions / 1000)


def budget_left(campaign: SponsorCampaign) -> bool:
    if campaign.budget is None:
        return True
    if campaign.pricing_model == PricingModel.FLAT.value:
        return True  # a flat fee is agreed up front; the budget caps nothing further
    return earned(campaign) < money(campaign.budget)


async def list_campaigns(db: Session, status: str | None = None) -> list[SponsorCampaign]:
    return await db.find(SponsorCampaign, {"status": status} if status else {}, sort=[("created_at", -1)], limit=500)


# --- Serving and measurement -------------------------------------------------------------------------------


def _sign(payload: str) -> str:
    digest = hmac.new(derive_key("sponsored-view"), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:18]).decode().rstrip("=")


def view_token(campaign_id: uuid.UUID, placement: str, now: float | None = None) -> str:
    issued = int(now if now is not None else time.time())
    nonce = uuid.uuid4().hex[:12]
    return f"{issued}.{nonce}.{_sign(f'{campaign_id}:{placement}:{issued}:{nonce}')}"


def token_valid(token: str, campaign_id: uuid.UUID, placement: str, now: float | None = None) -> bool:
    try:
        issued_s, nonce, sig = token.split(".")
        issued = int(issued_s)
    except ValueError:
        return False
    age = (now if now is not None else time.time()) - issued
    if not 0 <= age <= TOKEN_TTL_SECONDS:
        return False
    return hmac.compare_digest(sig, _sign(f"{campaign_id}:{placement}:{issued}:{nonce}"))


def _eligible(campaign: SponsorCampaign, placement: str, now: datetime) -> bool:
    return (
        campaign.status == CampaignStatus.ACTIVE.value
        and placement in (campaign.placements or [])
        and (campaign.starts_at is None or campaign.starts_at <= now)
        and (campaign.ends_at is None or now < campaign.ends_at)
        and budget_left(campaign)
    )


async def serve(db: Session, placement: str) -> dict[str, Any]:
    if placement not in PLACEMENTS:
        raise HTTPException(status_code=404, detail="Unknown placement")
    config = await get_settings(db)
    slot = config.placements.get(placement) or {}
    if not config.enabled or not slot.get("enabled"):
        return {"placement": placement, "enabled": False, "items": []}
    now = utcnow()
    pool = [
        c
        for c in await db.find(SponsorCampaign, {"status": CampaignStatus.ACTIVE.value, "placements": placement})
        if _eligible(c, placement, now)
    ]
    chosen: list[SponsorCampaign] = []
    for _ in range(min(int(slot.get("max_items") or 1), len(pool))):
        pick = random.choices(pool, weights=[max(1, c.weight) for c in pool])[0]
        chosen.append(pick)
        pool.remove(pick)
    base = f"{settings.API_V1_PREFIX}/sponsored"
    items = []
    for c in chosen:
        token = view_token(c.id, placement)
        items.append(
            {
                "id": c.id,
                "sponsor": c.sponsor,
                "category": c.category,
                "headline": c.headline,
                "body": c.body,
                "cta_label": c.cta_label,
                "image_url": c.image_url,
                "token": token,
                "click_path": f"{base}/{c.id}/click?placement={placement}&token={token}",
            }
        )
    return {"placement": placement, "enabled": True, "items": items}


async def _first_use(kind: str, campaign_id: uuid.UUID, token: str) -> bool:
    key = hashlib.sha256(f"{kind}:{campaign_id}:{token}".encode()).hexdigest()
    try:
        await SponsorView.get_pymongo_collection().insert_one(
            {"_id": uuid.uuid4(), "key_hash": key, "created_at": utcnow()}
        )
    except DuplicateKeyError:
        return False
    return True


async def record(db: Session, campaign_id: str, placement: str, token: str, kind: str) -> bool:
    """Count one impression or click. False (and nothing counted) for a bad, expired or reused token, or a
    campaign that is no longer active. Counters are atomic increments outside any transaction."""
    cid = parse_uuid(campaign_id, "Campaign")
    if placement not in PLACEMENTS or not token_valid(token, cid, placement):
        return False
    campaign = await db.get(SponsorCampaign, cid)
    if campaign is None or campaign.status != CampaignStatus.ACTIVE.value:
        return False
    if not await _first_use(kind, cid, token):
        return False
    field = "impressions" if kind == "impression" else "clicks"
    day = utcnow().date().isoformat()
    await SponsorStat.get_pymongo_collection().update_one(
        {"campaign_id": cid, "day": day, "placement": placement},
        {"$inc": {field: 1}, "$setOnInsert": {"_id": uuid.uuid4()}},
        upsert=True,
    )
    await SponsorCampaign.get_pymongo_collection().update_one({"_id": cid}, {"$inc": {field: 1}})
    return True


async def click_target(db: Session, campaign_id: str, placement: str, token: str) -> str:
    """Count a click (if valid) and return where to send the viewer: always the campaign's stored URL."""
    campaign = await get_campaign(db, campaign_id)
    await record(db, campaign_id, placement, token, "click")
    return campaign.target_url


# --- Reporting ---------------------------------------------------------------------------------------------


async def stats(db: Session, campaign_ids: list[uuid.UUID], since: datetime) -> dict[uuid.UUID, dict[str, int]]:
    rows = await db.aggregate(
        SponsorStat,
        [
            {"$match": {"campaign_id": {"$in": campaign_ids}, "day": {"$gte": since.date().isoformat()}}},
            {"$group": {"_id": "$campaign_id", "impressions": {"$sum": "$impressions"}, "clicks": {"$sum": "$clicks"}}},
        ],
    )
    return {r["_id"]: {"impressions": int(r["impressions"]), "clicks": int(r["clicks"])} for r in rows}


async def revenue_by_day(db: Session, since: datetime) -> dict[str, dict[str, Decimal]]:
    """Sponsorship revenue per UTC day: CPM and CPC from that day's counts, flat fees on the campaign's start day."""
    campaigns = {c.id: c for c in await db.find(SponsorCampaign)}
    out: dict[str, dict[str, Decimal]] = {}

    def add(day: str, amount: Decimal) -> None:
        if amount:
            out.setdefault(day, {"sponsorship": Decimal(0)})["sponsorship"] += amount

    for row in await db.find(SponsorStat, {"day": {"$gte": since.date().isoformat()}}):
        c = campaigns.get(row.campaign_id)
        if c is None:
            continue
        rate = money(c.rate or 0)
        if c.pricing_model == PricingModel.CPM.value:
            add(row.day, money(rate * row.impressions / 1000))
        elif c.pricing_model == PricingModel.CPC.value:
            add(row.day, money(rate * row.clicks))
    for c in campaigns.values():
        start = c.starts_at or c.created_at
        if c.pricing_model == PricingModel.FLAT.value and c.status != CampaignStatus.DRAFT.value and start >= since:
            add(start.date().isoformat(), money(c.rate or 0))
    return out


def campaign_view(c: SponsorCampaign, window: dict[str, int] | None = None) -> dict[str, Any]:
    ctr = round(c.clicks / c.impressions, 4) if c.impressions else None
    now = utcnow()
    return {
        **c.model_dump(exclude={"revision_id"}),
        "earned": earned(c),
        "ctr": ctr,
        "serving": any(_eligible(c, p, now) for p in c.placements or []),
        "last_30_days": window or {"impressions": 0, "clicks": 0},
    }


def since_days(days: int) -> datetime:
    return utcnow() - timedelta(days=days)
