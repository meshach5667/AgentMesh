"""Sponsored placements and referral links: campaigns, the platform's advertising settings, and their measured
views and clicks.

A lightweight foundation only: AgentMesh does not bill advertisers or track conversions. Agreements with sponsors and
referral partners live outside the platform; what is stored here is what to show, where, when, and how often it was
genuinely seen and clicked. Sponsored content never influences placement, health checks or any security decision.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.core.timeutil import utcnow
from app.documents.base import Doc, index, unique


class CampaignStatus(str, enum.Enum):  # noqa: UP042
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class SponsorCategory(str, enum.Enum):  # noqa: UP042
    GPU_CLOUD = "gpu_cloud"
    AI_INFERENCE = "ai_inference"
    MODEL_HOSTING = "model_hosting"
    CLOUD_INFRASTRUCTURE = "cloud_infrastructure"
    DATA_CENTER = "data_center"
    DEVELOPER_TOOLS = "developer_tools"
    # Earlier categories, kept so existing campaigns stay valid.
    AI_TOOLS = "ai_tools"
    GPU_HARDWARE = "gpu_hardware"
    INFRASTRUCTURE = "infrastructure"


class CampaignKind(str, enum.Enum):  # noqa: UP042
    SPONSORED = "sponsored"  # a sponsored listing, resource, tutorial or banner, labelled "Sponsored"
    REFERRAL = "referral"  # an outbound referral or affiliate link, labelled "Referral link"


class AdSettings(Doc):
    """The single advertising settings document (id SETTINGS_ID). Advertising is off until an operator enables it."""

    enabled: bool = False
    # placement key -> {"enabled": bool, "max_items": int}; keys come from sponsorship_service.PLACEMENTS.
    placements: dict[str, dict[str, Any]] = Field(default_factory=dict)
    updated_by: uuid.UUID | None = None
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "ad_settings"


class SponsorCampaign(Doc):
    name: str  # internal name
    sponsor: str  # shown to users
    category: str
    headline: str
    body: str | None = None
    cta_label: str = "Learn more"
    target_url: str
    image_url: str | None = None
    placements: list[str] = Field(default_factory=list)
    status: str = CampaignStatus.DRAFT.value
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    weight: int = 1  # relative chance of being shown among eligible campaigns
    kind: str = CampaignKind.SPONSORED.value
    # Referral metadata appended to target_url on click (?ref=...&utm_campaign=...); agreed outside the platform.
    referral_code: str | None = None
    utm_campaign: str | None = None
    impressions: int = 0
    clicks: int = 0
    created_by: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "sponsor_campaigns"
        indexes = [index("status"), index("created_at")]


class SponsorStat(Doc):
    """Impressions and clicks of one campaign in one placement on one UTC day."""

    campaign_id: uuid.UUID
    day: str  # YYYY-MM-DD
    placement: str
    impressions: int = 0
    clicks: int = 0

    class Settings(Doc.Settings):
        name = "sponsor_stats"
        indexes = [unique("campaign_id", "day", "placement", name="uq_sponsor_stats_day"), index("day")]


class SponsorView(Doc):
    """A view token already counted (as an impression or a click), so each is counted once. Expires after a day."""

    key_hash: str
    created_at: datetime = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "sponsor_views"
        indexes = [
            unique("key_hash", name="uq_sponsor_views_key"),
            IndexModel([("created_at", ASCENDING)], name="ttl_sponsor_views", expireAfterSeconds=86400),
        ]
