"""Revenue analytics for the dashboards, computed from rated charges, refunds and payments (never estimated).

Compute charges are the primary revenue: customers pay the gross, providers are credited their share, and the
platform keeps the commission. Refunds reduce each of those. Sponsorships are a separate, supplementary stream
reported next to it (network scope only), never mixed into compute figures.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.billing import Charge, Payment, PaymentStatus, Payout, PayoutStatus, Refund, RefundKind, RefundStatus
from app.documents.deployment import Deployment
from app.documents.node import Node
from app.documents.user import User
from app.services import ledger_service
from app.services.ledger_service import money

DAY = {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}


def _days(since: datetime, days: int) -> list[str]:
    start = since.date()
    return [(start + timedelta(days=i)).isoformat() for i in range(days + 1)]


async def _by_day(db: Session, doc: type, match: dict, fields: dict[str, str]) -> dict[str, dict[str, Decimal]]:
    rows = await db.aggregate(
        doc,
        [{"$match": match}, {"$group": {"_id": DAY, **{k: {"$sum": f"${v}"} for k, v in fields.items()}}}],
    )
    return {r["_id"]: {k: money(r.get(k) or 0) for k in fields} for r in rows}


async def _top(db: Session, match: dict, key: str, limit: int = 10) -> list[dict[str, Any]]:
    rows = await db.aggregate(
        Charge,
        [
            {"$match": match},
            {
                "$group": {
                    "_id": f"${key}",
                    "gross": {"$sum": "$amount"},
                    "platform_fee": {"$sum": "$platform_fee"},
                    "provider_share": {"$sum": "$provider_amount"},
                    "charges": {"$sum": 1},
                }
            },
            {"$sort": {"gross": -1}},
            {"$limit": limit},
        ],
    )
    return [
        {
            "id": r["_id"],
            "charges": int(r["charges"]),
            "gross": money(r["gross"]),
            "platform_fee": money(r["platform_fee"]),
            "provider_share": money(r["provider_share"]),
        }
        for r in rows
        if r["_id"] is not None
    ]


async def _wallet_emails(db: Session, wallet_ids: list[Any]) -> dict[Any, str]:
    from app.documents.wallet import Wallet

    wallets = await db.find(Wallet, {"_id": {"$in": wallet_ids}})
    users = {u.id: u.email for u in await db.find(User, {"_id": {"$in": [w.user_id for w in wallets]}})}
    return {w.id: users.get(w.user_id, "") if w.user_id else "" for w in wallets}


async def revenue(db: Session, user: User, scope: str, days: int) -> dict[str, Any]:
    """Daily compute revenue and refunds for the caller's scope ("customer", "provider" or "network"), with totals
    and the biggest contributors. Network scope adds payments, payouts and sponsorship revenue."""
    since = (utcnow() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    charge_match: dict[str, Any] = {"created_at": {"$gte": since}}
    refund_match: dict[str, Any] = {
        "created_at": {"$gte": since},
        "kind": RefundKind.CHARGE.value,
        "status": RefundStatus.SUCCEEDED.value,
    }
    if scope != "network":
        wallet = await ledger_service.wallet_for_user(db, user.id)
        field = "customer_wallet_id" if scope == "customer" else "provider_wallet_id"
        charge_match[field] = wallet.id
        refund_match["wallet_id" if scope == "customer" else "provider_wallet_id"] = wallet.id

    charges = await _by_day(
        db,
        Charge,
        charge_match,
        {"gross": "amount", "platform_fee": "platform_fee", "provider_share": "provider_amount"},
    )
    refunds = await _by_day(
        db, Refund, refund_match, {"refunded": "amount", "fee_reversed": "platform_fee", "clawback": "provider_amount"}
    )
    extra: dict[str, dict[str, dict[str, Decimal]]] = {}
    if scope == "network":
        extra["topups"] = await _by_day(
            db, Payment, {"status": PaymentStatus.SUCCEEDED.value, "created_at": {"$gte": since}}, {"topups": "amount"}
        )
        extra["payouts"] = await _by_day(
            db, Payout, {"status": PayoutStatus.SUCCEEDED.value, "created_at": {"$gte": since}}, {"payouts": "amount"}
        )
        extra["card_refunds"] = await _by_day(
            db,
            Refund,
            {"kind": RefundKind.TOPUP.value, "status": RefundStatus.SUCCEEDED.value, "created_at": {"$gte": since}},
            {"card_refunds": "amount"},
        )
        from app.services import sponsorship_service

        extra["sponsorship"] = await sponsorship_service.revenue_by_day(db, since)

    zero = Decimal(0)
    series = []
    for day in _days(since, days):
        c, r = charges.get(day, {}), refunds.get(day, {})
        point: dict[str, Any] = {
            "date": day,
            "gross": c.get("gross", zero),
            "platform_fee": c.get("platform_fee", zero),
            "provider_share": c.get("provider_share", zero),
            "refunded": r.get("refunded", zero),
            "fee_reversed": r.get("fee_reversed", zero),
            "clawback": r.get("clawback", zero),
        }
        for name, values in extra.items():
            point |= values.get(day, {}) or {name: zero}
        series.append(point)

    keys = [k for k in series[0] if k != "date"]
    totals = {k: sum((p[k] for p in series), zero) for k in keys}
    totals["net_platform_commission"] = totals["platform_fee"] - totals["fee_reversed"]
    totals["net_provider_earnings"] = totals["provider_share"] - totals["clawback"]
    totals["net_customer_spend"] = totals["gross"] - totals["refunded"]
    if scope == "network":
        totals["platform_revenue"] = totals["net_platform_commission"] + totals["sponsorship"]

    breakdown: list[dict[str, Any]] = []
    if scope == "customer":
        breakdown = await _top(db, charge_match, "deployment_id")
        names = {d.id: d.model_tag for d in await db.find(Deployment, {"_id": {"$in": [b["id"] for b in breakdown]}})}
        breakdown = [b | {"label": names.get(b["id"]) or str(b["id"])[:8]} for b in breakdown]
    elif scope == "provider":
        breakdown = await _top(db, charge_match, "node_id")
        names = {n.id: n.name for n in await db.find(Node, {"_id": {"$in": [b["id"] for b in breakdown]}})}
        breakdown = [b | {"label": names.get(b["id"]) or str(b["id"])[:8]} for b in breakdown]
    else:
        breakdown = await _top(db, charge_match, "provider_wallet_id")
        emails = await _wallet_emails(db, [b["id"] for b in breakdown])
        breakdown = [b | {"label": emails.get(b["id"]) or str(b["id"])[:8]} for b in breakdown]

    return {
        "scope": scope,
        "days": days,
        "since": since,
        "currency": settings.BILLING_CURRENCY,
        "series": series,
        "totals": totals,
        "breakdown": breakdown,
        "breakdown_by": {"customer": "deployment", "provider": "node", "network": "provider"}[scope],
    }
