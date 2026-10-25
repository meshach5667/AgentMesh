"""Phase 3: optional sponsored placements: settings, campaign validation and lifecycle, serving, measurement,
budgets and revenue."""

import time
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.timeutil import utcnow
from app.documents import SponsorCampaign, SponsorStat
from app.services import sponsorship_service

CAMPAIGN = {
    "name": "GPU spring promo",
    "sponsor": "Acme GPUs",
    "category": "gpu_hardware",
    "headline": "Rent an H100 by the hour",
    "body": "Bare-metal GPUs for inference.",
    "target_url": "https://acme.example/gpus?ref=agentmesh",
    "placements": ["landing", "customer_dashboard"],
    "pricing_model": "cpm",
    "rate": "1000",
}


@pytest.fixture
async def operator(make_user):
    return (await make_user("operator"))[1]


async def _enable(client, operator, **placements):
    slots = {k: {"enabled": True, "max_items": v} for k, v in (placements or {"landing": 1}).items()}
    resp = await client.put("/api/v1/admin/ads/settings", json={"enabled": True, "placements": slots}, headers=operator)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _campaign(client, operator, activate=True, **over):
    resp = await client.post("/api/v1/admin/ads/campaigns", json=CAMPAIGN | over, headers=operator)
    assert resp.status_code == 201, resp.text
    campaign = resp.json()
    if activate:
        resp = await client.post(
            f"/api/v1/admin/ads/campaigns/{campaign['id']}/status", json={"status": "active"}, headers=operator
        )
        assert resp.status_code == 200, resp.text
        campaign = resp.json()
    return campaign


async def _serve(client, placement="landing"):
    resp = await client.get(f"/api/v1/sponsored?placement={placement}")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_advertising_is_off_until_an_operator_enables_it(client, make_user, operator):
    await _campaign(client, operator)
    assert await _serve(client) == {"placement": "landing", "enabled": False, "items": []}
    _, customer = await make_user("customer")
    assert (await client.get("/api/v1/admin/ads/settings", headers=customer)).status_code == 403
    settings = (await client.get("/api/v1/admin/ads/settings", headers=operator)).json()
    assert settings["enabled"] is False and {p["key"] for p in settings["placements"]} == set(
        sponsorship_service.PLACEMENTS
    )
    bad = await client.put(
        "/api/v1/admin/ads/settings", json={"placements": {"popup": {"enabled": True}}}, headers=operator
    )
    assert bad.status_code == 422
    too_many = await client.put(
        "/api/v1/admin/ads/settings",
        json={"placements": {"landing": {"enabled": True, "max_items": 9}}},
        headers=operator,
    )
    assert too_many.status_code == 422

    await _enable(client, operator)
    served = await _serve(client)
    assert served["enabled"] and served["items"][0]["sponsor"] == "Acme GPUs"
    assert (await _serve(client, "docs"))["enabled"] is False  # this slot stays off
    assert (await client.get("/api/v1/sponsored?placement=nowhere")).status_code == 404
    audit = (await client.get("/api/v1/admin/audit-logs?action=ads.settings_updated", headers=operator)).json()
    assert len(audit) == 1


@pytest.mark.parametrize(
    "over",
    [
        {"target_url": "http://acme.example"},
        {"target_url": "javascript:alert(1)"},
        {"image_url": "data:image/png;base64,AAAA"},
        {"placements": ["popup"]},
        {"placements": []},
        {"category": "gambling"},
        {"headline": "x"},
        {"rate": "-1"},
        {"starts_at": "2026-12-02T00:00:00", "ends_at": "2026-12-01T00:00:00"},
    ],
)
async def test_campaign_validation(client, operator, over):
    assert (await client.post("/api/v1/admin/ads/campaigns", json=CAMPAIGN | over, headers=operator)).status_code == 422


async def test_campaign_lifecycle(client, operator):
    await _enable(client, operator)
    draft = await _campaign(client, operator, activate=False)
    assert draft["status"] == "draft" and (await _serve(client))["items"] == []
    url = f"/api/v1/admin/ads/campaigns/{draft['id']}/status"
    assert (await client.post(url, json={"status": "paused"}, headers=operator)).status_code == 409
    assert (await client.post(url, json={"status": "active"}, headers=operator)).json()["serving"] is True
    assert len((await _serve(client))["items"]) == 1
    await client.post(url, json={"status": "paused"}, headers=operator)
    assert (await _serve(client))["items"] == []
    edited = await client.put(
        f"/api/v1/admin/ads/campaigns/{draft['id']}", json=CAMPAIGN | {"headline": "New headline"}, headers=operator
    )
    assert edited.json()["headline"] == "New headline"
    await client.post(url, json={"status": "ended"}, headers=operator)
    assert (await client.post(url, json={"status": "active"}, headers=operator)).status_code == 409
    assert (
        await client.put(f"/api/v1/admin/ads/campaigns/{draft['id']}", json=CAMPAIGN, headers=operator)
    ).status_code == 409


async def test_schedule_window_is_respected(client, operator):
    await _enable(client, operator)
    later = (utcnow() + timedelta(days=1)).isoformat()
    await _campaign(client, operator, starts_at=later)
    assert (await _serve(client))["items"] == []
    await _campaign(client, operator, ends_at=(utcnow() - timedelta(minutes=1)).isoformat(), starts_at=None)
    assert (await _serve(client))["items"] == []


async def test_impressions_are_counted_once_per_valid_token(client, db, operator):
    await _enable(client, operator)
    campaign = await _campaign(client, operator)
    item = (await _serve(client))["items"][0]
    url = f"/api/v1/sponsored/{campaign['id']}/impression"
    assert (await client.post(url, json={"placement": "landing", "token": item["token"]})).json() == {"counted": True}
    assert (await client.post(url, json={"placement": "landing", "token": item["token"]})).json() == {"counted": False}
    forged = item["token"].rsplit(".", 1)[0] + ".AAAAAAAAAAAAAAAAAAAAAAAA"
    assert (await client.post(url, json={"placement": "landing", "token": forged})).json()["counted"] is False
    other_slot = await client.post(url, json={"placement": "customer_dashboard", "token": item["token"]})
    assert other_slot.json()["counted"] is False
    expired = sponsorship_service.view_token(uuid.UUID(campaign["id"]), "landing", time.time() - 7200)
    assert (await client.post(url, json={"placement": "landing", "token": expired})).json()["counted"] is False

    db.expire_all()
    assert (await db.get(SponsorCampaign, uuid.UUID(campaign["id"]))).impressions == 1
    stat = await db.find_one(SponsorStat)
    assert (stat.placement, stat.impressions, stat.clicks) == ("landing", 1, 0)


async def test_clicks_redirect_to_the_campaign_url_and_count_once(client, db, operator):
    await _enable(client, operator)
    campaign = await _campaign(client, operator)
    item = (await _serve(client))["items"][0]
    resp = await client.get(item["click_path"].removeprefix(""), follow_redirects=False)
    assert resp.status_code == 302 and resp.headers["location"] == CAMPAIGN["target_url"]
    assert resp.headers["referrer-policy"] == "no-referrer"
    await client.get(item["click_path"], follow_redirects=False)  # replayed: not counted
    bad = await client.get(
        f"/api/v1/sponsored/{campaign['id']}/click?placement=landing&token=nope", follow_redirects=False
    )
    assert bad.status_code == 302 and bad.headers["location"] == CAMPAIGN["target_url"]
    db.expire_all()
    assert (await db.get(SponsorCampaign, uuid.UUID(campaign["id"]))).clicks == 1
    unknown = await client.get(f"/api/v1/sponsored/{uuid.uuid4()}/click?placement=landing&token=x")
    assert unknown.status_code == 404


async def test_budget_stops_serving(client, operator):
    await _enable(client, operator)
    campaign = await _campaign(client, operator, pricing_model="cpc", rate="10", budget="20")
    for _ in range(2):
        item = (await _serve(client))["items"][0]
        await client.get(item["click_path"], follow_redirects=False)
    assert (await _serve(client))["items"] == []
    listed = (await client.get("/api/v1/admin/ads/campaigns", headers=operator)).json()
    row = next(c for c in listed if c["id"] == campaign["id"])
    assert Decimal(row["earned"]) == Decimal(20) and row["serving"] is False and row["last_30_days"]["clicks"] == 2


async def test_slot_shows_distinct_campaigns_up_to_its_limit(client, operator):
    await _enable(client, operator, landing=2)
    for name in ("A", "B", "C"):
        await _campaign(client, operator, sponsor=f"Sponsor {name}")
    items = (await _serve(client))["items"]
    assert len(items) == 2 and len({i["id"] for i in items}) == 2


async def test_sponsorship_revenue_is_a_separate_stream(client, operator):
    await _enable(client, operator)
    campaign = await _campaign(client, operator)  # CPM 1000: 1 per impression
    for _ in range(3):
        item = (await _serve(client))["items"][0]
        await client.post(
            f"/api/v1/sponsored/{campaign['id']}/impression", json={"placement": "landing", "token": item["token"]}
        )
    await _campaign(client, operator, pricing_model="flat", rate="500", placements=["docs"])
    network = (await client.get("/api/v1/analytics/revenue?scope=network", headers=operator)).json()
    assert Decimal(network["totals"]["sponsorship"]) == Decimal(503)
    assert Decimal(network["totals"]["platform_revenue"]) == Decimal(503)  # no compute charges in this test
    assert Decimal(network["totals"]["gross"]) == 0
