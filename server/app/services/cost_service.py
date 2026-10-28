"""Cost estimates: what a deployment's use of a machine costs at that machine's published prices.

AgentMesh moves no money and keeps no balances. Customers pay providers directly, on the provider's terms; these
estimates show both sides what the usage comes to. Nothing is deducted, split, or stopped for lack of funds.

What is estimated, per deployment and machine, at the machine's prices (never above the rates in force when the
deployment was placed there, see node_pricing_service):

* READY time x reserved resources (CPU cores, RAM, VRAM). READY intervals come from the control plane's own
  lifecycle events, not from the worker. UNHEALTHY time is not counted.
* Input/output tokens at the per-million prices, for successful requests only. Counts are runtime-reported (see
  UsageRecord.token_source) and bounded by the bytes the gateway measured.

A background job estimates each deployment's window [metered_until, now) at most every COST_ESTIMATE_INTERVAL_SECONDS,
splitting at price changes and node changes. Each (deployment, node, period_start) produces at most one estimate
(unique index) and the watermark advances with a compare-and-set, so concurrent replicas cannot double count.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.core.config import settings
from app.core.database import Session, session_scope
from app.core.timeutil import utcnow
from app.documents.billing import CostEstimate
from app.documents.deployment import Deployment, DeploymentEvent
from app.documents.deployment import DeploymentStatus as S
from app.documents.node import Node
from app.documents.reservation import ResourceReservation
from app.documents.usage import UsageRecord
from app.documents.user import Customer, Provider, User
from app.services import credit_service
from app.services.node_pricing_service import Rates, estimated_rates, node_price_changes

logger = logging.getLogger(__name__)

SECONDS_PER_HOUR = Decimal(3600)
MILLION = Decimal(1_000_000)
CENT = Decimal("0.00000001")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


# --- Measurement -------------------------------------------------------------------------------------------


@dataclass
class Interval:
    start: datetime
    end: datetime
    node_id: uuid.UUID | None


def ready_intervals(events: list[DeploymentEvent], now: datetime, fallback_node: uuid.UUID | None) -> list[Interval]:
    """READY periods from the lifecycle history (state changes only, in time order)."""
    out: list[Interval] = []
    opened: tuple[datetime, uuid.UUID | None] | None = None
    for e in events:
        if e.to_status is None:
            continue  # progress note
        if e.to_status == S.READY.value and opened is None:
            opened = (e.created_at, e.node_id or fallback_node)
        elif e.to_status == S.READY.value and opened is not None and e.node_id and e.node_id != opened[1]:
            # Planned move: READY continues on another node from this instant.
            out.append(Interval(opened[0], e.created_at, opened[1]))
            opened = (e.created_at, e.node_id)
        elif e.to_status != S.READY.value and opened is not None:
            out.append(Interval(opened[0], e.created_at, opened[1]))
            opened = None
    if opened is not None:
        out.append(Interval(opened[0], now, opened[1]))
    return out


def _clip(intervals: list[Interval], start: datetime, end: datetime) -> dict[uuid.UUID | None, float]:
    seconds: dict[uuid.UUID | None, float] = {}
    for iv in intervals:
        lo, hi = max(iv.start, start), min(iv.end, end)
        if hi > lo:
            seconds[iv.node_id] = seconds.get(iv.node_id, 0.0) + (hi - lo).total_seconds()
    return seconds


# Tokens a runtime may add to a request for its chat template and default system prompt.
TEMPLATE_TOKENS = 1024


async def _tokens(db: Session, dep_id: uuid.UUID, start: datetime, end: datetime) -> dict:
    rows = await db.aggregate(
        UsageRecord,
        [
            {
                "$match": {
                    "deployment_id": dep_id,
                    "kind": "inference",
                    "outcome": "success",  # failed, cancelled or timed-out requests are not counted
                    "created_at": {"$gte": start, "$lt": end},
                }
            },
            {
                "$group": {
                    "_id": "$node_id",
                    # Input tokens: at most the forwarded request's bytes plus the runtime's chat template.
                    "input": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$ne": [{"$ifNull": ["$request_bytes", None]}, None]},
                                        {"$gt": ["$input_tokens", {"$add": ["$request_bytes", TEMPLATE_TOKENS]}]},
                                    ]
                                },
                                {"$add": ["$request_bytes", TEMPLATE_TOKENS]},
                                "$input_tokens",
                            ]
                        }
                    },
                    # Output tokens are reported by the provider's runtime. Bound them by the response bytes the
                    # gateway itself counted (every token costs at least one byte), so they cannot be inflated.
                    "output": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$ne": [{"$ifNull": ["$response_bytes", None]}, None]},
                                        {"$gt": ["$output_tokens", "$response_bytes"]},
                                    ]
                                },
                                "$response_bytes",
                                "$output_tokens",
                            ]
                        }
                    },
                }
            },
        ],
    )
    return {r["_id"]: (int(r["input"] or 0), int(r["output"] or 0)) for r in rows}


async def _reservation(db: Session, dep_id: uuid.UUID, node_id: uuid.UUID | None) -> ResourceReservation | None:
    if node_id is None:
        return None
    return await db.find_one(
        ResourceReservation, {"deployment_id": dep_id, "node_id": node_id}, sort=[("created_at", -1)]
    )


def price(rates: Rates, ready_seconds: float, cpu: int, ram_mb: int, vram_mb: int, tin: int, tout: int):
    hours = Decimal(str(ready_seconds)) / SECONDS_PER_HOUR
    resource = money(rates.hourly(cpu, ram_mb, vram_mb) * hours)
    tokens = money((rates.input_tokens_per_million * tin + rates.output_tokens_per_million * tout) / MILLION)
    return resource, tokens, resource + tokens


async def _cuts(db: Session, node_id: uuid.UUID | None, start: datetime, end: datetime) -> list[datetime]:
    """Boundaries of [start, end) where this node's prices change."""
    points = {start, end}
    if node_id is not None:
        points.update(await node_price_changes(db, node_id, start, end))
    return sorted(points)


# --- Estimating --------------------------------------------------------------------------------------------


async def estimate_deployment(db: Session, dep: Deployment, now: datetime) -> list[CostEstimate]:
    """Estimate [metered_until, now) for one deployment. Does not commit; raises on a lost race."""
    start = dep.metered_until or dep.created_at
    events = await db.find(
        DeploymentEvent, {"deployment_id": dep.id, "to_status": {"$ne": None}}, sort=[("created_at", 1)]
    )
    intervals = ready_intervals(events, now, dep.node_id)
    out: list[CostEstimate] = []
    for node_id in set(_clip(intervals, start, now)) | set(await _tokens(db, dep.id, start, now)):
        if node_id is None:
            continue
        reservation = await _reservation(db, dep.id, node_id)
        cpu, ram, vram = (reservation.cpu_cores, reservation.ram_mb, reservation.vram_mb) if reservation else (0, 0, 0)
        placed_at = reservation.rates if reservation else None
        node = await db.get(Node, node_id)
        cuts = await _cuts(db, node_id, start, now)
        for seg_start, seg_end in zip(cuts, cuts[1:], strict=False):
            rates = await estimated_rates(db, node_id, placed_at, seg_start)
            if rates is None or rates.is_free():
                continue  # free machine: usage is measured, nothing is owed
            ready_s = _clip(intervals, seg_start, seg_end).get(node_id, 0.0)
            tin, tout = (await _tokens(db, dep.id, seg_start, seg_end)).get(node_id, (0, 0))
            resource, token_amt, amount = price(rates, ready_s, cpu, ram, vram, tin, tout)
            if amount <= 0:
                continue
            estimate = CostEstimate(
                deployment_id=dep.id,
                node_id=node_id,
                customer_id=dep.customer_id,
                provider_id=node.owner_id if node else None,
                node_price_id=rates.node_price_id,
                rates=rates.snapshot(),
                period_start=seg_start,
                period_end=seg_end,
                ready_seconds=round(ready_s, 3),
                cpu_cores=cpu,
                ram_mb=ram,
                vram_mb=vram,
                input_tokens=tin,
                output_tokens=tout,
                resource_amount=resource,
                token_amount=token_amt,
                amount=amount,
                currency=rates.currency,
            )
            db.add(estimate)
            out.append(estimate)
            if dep.customer_id is not None and estimate.provider_id is not None:
                await credit_service.post(
                    db,
                    customer_id=dep.customer_id,
                    provider_id=estimate.provider_id,
                    currency=estimate.currency,
                    amount=-amount,
                    kind="usage",
                    key=f"estimate:{estimate.id}",
                    estimate_id=estimate.id,
                    deployment_id=dep.id,
                )
    moved = await db.update_one(
        Deployment, {"_id": dep.id, "metered_until": dep.metered_until}, {"$set": {"metered_until": now}}
    )
    if not moved:
        raise RuntimeError(f"Estimate watermark for deployment {dep.id} moved concurrently")
    dep.metered_until = now
    if dep.priced and dep.customer_id and dep.credit_provider_id and dep.credit_currency:
        left = await credit_service.balance(db, dep.customer_id, dep.credit_provider_id, dep.credit_currency)
        if left <= 0:
            from app.services import placement_service

            await placement_service.pause_for_credit(db, dep)
    return out


async def due_deployments(db: Session, now: datetime) -> list[Deployment]:
    rows = await db.find(
        Deployment,
        {
            "was_ready": True,
            "$or": [
                {"metered_until": None},
                {"ended_at": None},
                {"$expr": {"$lt": ["$metered_until", "$ended_at"]}},
            ],
        },
    )
    interval = timedelta(seconds=settings.COST_ESTIMATE_INTERVAL_SECONDS)
    return [d for d in rows if d.ended_at is not None or now - (d.metered_until or d.created_at) >= interval]


async def run_estimates(now: datetime | None = None) -> int:
    """Estimate every deployment that is due. Each deployment is its own transaction. Returns estimates created."""
    now = now or utcnow()
    created = 0
    async with session_scope() as db:
        ids = [d.id for d in await due_deployments(db, now)]
    for dep_id in ids:
        async with session_scope() as db:
            dep = await db.get(Deployment, dep_id)
            if dep is None:
                continue
            try:
                estimates = await estimate_deployment(db, dep, now)
                await db.commit()
                created += len(estimates)
            except Exception:  # noqa: BLE001 - one bad deployment must not stop estimates for the rest
                await db.rollback()
                logger.exception("Cost estimate failed for deployment %s", dep_id)
    return created


# --- Views -------------------------------------------------------------------------------------------------


async def scope_filter(db: Session, user: User, scope: str) -> dict:
    """Estimates the caller may see: as the customer who used the machine, or the provider who runs it."""
    if scope == "network":
        return {}
    if scope == "customer":
        customer = await db.find_one(Customer, {"user_id": user.id})
        return {"customer_id": customer.id if customer else None}
    provider = await db.find_one(Provider, {"user_id": user.id})
    return {"provider_id": provider.id if provider else None}


async def summary(db: Session, match: dict, days: int) -> dict:
    """Estimated totals per currency and per day for the estimates matching ``match`` over the last ``days``."""
    since = utcnow() - timedelta(days=days)
    rows = await db.aggregate(
        CostEstimate,
        [
            {"$match": match | {"period_start": {"$gte": since}}},
            {
                "$group": {
                    "_id": {
                        "currency": "$currency",
                        "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$period_start"}},
                    },
                    "amount": {"$sum": "$amount"},
                    "resource_amount": {"$sum": "$resource_amount"},
                    "token_amount": {"$sum": "$token_amount"},
                    "ready_seconds": {"$sum": "$ready_seconds"},
                    "deployments": {"$addToSet": "$deployment_id"},
                }
            },
            {"$sort": {"_id.day": 1}},
        ],
    )
    totals: dict[str, dict] = {}
    days_out = []
    for r in rows:
        cur, day = r["_id"]["currency"], r["_id"]["day"]
        amount = money(_dec(r["amount"]))
        t = totals.setdefault(
            cur,
            {
                "currency": cur,
                "amount": Decimal(0),
                "resource_amount": Decimal(0),
                "token_amount": Decimal(0),
                "ready_hours": 0.0,
            },
        )
        t["amount"] += amount
        t["resource_amount"] += money(_dec(r["resource_amount"]))
        t["token_amount"] += money(_dec(r["token_amount"]))
        t["ready_hours"] += float(r["ready_seconds"] or 0) / 3600
        days_out.append({"day": day, "currency": cur, "amount": amount, "deployments": len(r["deployments"])})
    return {
        "days": days,
        "since": since,
        "totals": [t | {"ready_hours": round(t["ready_hours"], 2)} for t in totals.values()],
        "by_day": days_out,
    }


def _dec(v) -> Decimal:
    return v.to_decimal() if hasattr(v, "to_decimal") else Decimal(str(v or 0))
