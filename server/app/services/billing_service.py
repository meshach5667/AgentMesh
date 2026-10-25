"""Pricing and rating: turns measured usage into charges and ledger postings.

What is charged, per deployment and node:

* READY time x reserved resources (CPU cores, RAM, VRAM) at the pricing version in force. READY intervals come
  from the control plane's own lifecycle events, not from the worker. UNHEALTHY time is not charged.
* Input/output tokens at the per-million prices. Counts are runtime-reported (see UsageRecord.token_source);
  requests without counts are not charged for tokens.

A background job rates each deployment's window [metered_until, now) at most every BILLING_INTERVAL_SECONDS,
splitting at pricing-version boundaries and node changes. Each (deployment, node, period_start) produces at most
one Charge (unique constraint) and advances the watermark with a compare-and-set, so concurrent replicas cannot
double-charge. Settlement debits the customer, credits the provider, and records the platform fee; the
customer's balance may go below zero by at most one window, after which their deployments are stopped.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import Session, session_scope
from app.core.timeutil import utcnow
from app.documents.billing import Charge, PricingRule
from app.documents.deployment import Deployment, DeploymentEvent
from app.documents.deployment import DeploymentStatus as S
from app.documents.node import Node
from app.documents.reservation import ResourceReservation
from app.documents.transaction import TransactionType
from app.documents.usage import UsageRecord
from app.documents.user import Customer, Provider, User
from app.services import audit_service, ledger_service
from app.services.ledger_service import money

logger = logging.getLogger(__name__)

MB_PER_GB = Decimal(1024)
SECONDS_PER_HOUR = Decimal(3600)
MILLION = Decimal(1_000_000)


# --- Pricing rules -----------------------------------------------------------------------------------------


async def active_rule(db: Session, at: datetime | None = None) -> PricingRule | None:
    at = at or utcnow()
    return await db.find_one(
        PricingRule, {"effective_from": {"$lte": at}}, sort=[("effective_from", -1), ("version", -1)]
    )


async def list_rules(db: Session) -> list[PricingRule]:
    return await db.find(PricingRule, sort=[("version", -1)])


async def create_rule(db: Session, data: dict, actor: User) -> PricingRule:
    """Add a new pricing version. Versions are immutable and cannot take effect in the past, so charges
    already rated are never re-priced."""
    now = utcnow()
    effective = data.pop("effective_from", None) or now
    if effective.tzinfo is not None:
        effective = effective.astimezone(UTC).replace(tzinfo=None)
    if effective < now - timedelta(seconds=60):
        raise HTTPException(status_code=422, detail="effective_from cannot be in the past")
    newest = await db.find_one(PricingRule, sort=[("version", -1)])
    latest = newest.version if newest else 0
    rule = PricingRule(
        id=uuid.uuid4(),
        version=latest + 1,
        currency=settings.BILLING_CURRENCY,
        effective_from=max(effective, now),
        created_by=actor.id,
        **data,
    )
    db.add(rule)
    audit_service.record(
        db,
        actor_id=actor.id,
        action="pricing.version_created",
        resource_type="pricing_rule",
        resource_id=rule.id,
        details={"version": rule.version, **{k: str(v) for k, v in data.items()}},
    )
    await db.commit()
    await db.refresh(rule)
    return rule


def hourly_resource_price(rule: PricingRule, cpu_cores: int, ram_mb: int, vram_mb: int) -> Decimal:
    return (
        Decimal(rule.cpu_core_hour) * cpu_cores
        + Decimal(rule.ram_gb_hour) * Decimal(ram_mb) / MB_PER_GB
        + Decimal(rule.vram_gb_hour) * Decimal(vram_mb) / MB_PER_GB
    )


def is_free(rule: PricingRule | None) -> bool:
    return rule is None or not any(
        Decimal(v)
        for v in (
            rule.cpu_core_hour,
            rule.ram_gb_hour,
            rule.vram_gb_hour,
            rule.input_tokens_per_million,
            rule.output_tokens_per_million,
        )
    )


async def require_prepaid(db: Session, user_id: uuid.UUID, cpu_cores: int, ram_mb: int, vram_mb: int) -> None:
    """Refuse a deployment the customer cannot afford for BILLING_MIN_PREPAID_HOURS of its reservation."""
    rule = await active_rule(db)
    if is_free(rule):
        return
    assert rule is not None
    hours = Decimal(str(settings.BILLING_MIN_PREPAID_HOURS))
    needed = money(hourly_resource_price(rule, cpu_cores, ram_mb, vram_mb) * hours)
    wallet = await ledger_service.wallet_for_user(db, user_id)
    have = await ledger_service.balance(db, wallet.id)
    if have < needed or have <= 0:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "insufficient_balance",
                "message": f"This deployment needs at least {needed} {rule.currency} in your wallet "
                f"({settings.BILLING_MIN_PREPAID_HOURS:g} h of its reserved resources); you have {money(have)}.",
                "required": str(needed),
                "balance": str(money(have)),
                "currency": rule.currency,
            },
        )


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


async def _tokens(db: Session, dep_id: uuid.UUID, start: datetime, end: datetime) -> dict:
    rows = await db.aggregate(
        UsageRecord,
        [
            {
                "$match": {
                    "deployment_id": dep_id,
                    "kind": "inference",
                    "created_at": {"$gte": start, "$lt": end},
                }
            },
            {
                "$group": {
                    "_id": "$node_id",
                    "input": {"$sum": "$input_tokens"},
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


async def _reservation(db: Session, dep_id: uuid.UUID, node_id: uuid.UUID | None) -> tuple[int, int, int]:
    if node_id is None:
        return 0, 0, 0
    res = await db.find_one(
        ResourceReservation, {"deployment_id": dep_id, "node_id": node_id}, sort=[("created_at", -1)]
    )
    return (res.cpu_cores, res.ram_mb, res.vram_mb) if res else (0, 0, 0)


async def _provider_user(db: Session, node_id: uuid.UUID | None) -> uuid.UUID | None:
    if node_id is None:
        return None
    node = await db.get(Node, node_id)
    provider = await db.get(Provider, node.owner_id) if node else None
    return provider.user_id if provider else None


# --- Rating ------------------------------------------------------------------------------------------------


def price(rule: PricingRule, ready_seconds: float, cpu: int, ram_mb: int, vram_mb: int, tin: int, tout: int):
    hours = Decimal(str(ready_seconds)) / SECONDS_PER_HOUR
    resource = money(hourly_resource_price(rule, cpu, ram_mb, vram_mb) * hours)
    tokens = money(
        (Decimal(rule.input_tokens_per_million) * tin + Decimal(rule.output_tokens_per_million) * tout) / MILLION
    )
    amount = resource + tokens
    fee = money(amount * Decimal(rule.platform_fee_rate))
    return resource, tokens, amount, amount - fee, fee


async def _rules_in(db: Session, start: datetime, end: datetime) -> list[tuple[datetime, PricingRule | None]]:
    """(segment start, rule) for each pricing segment of [start, end)."""
    later = await db.find(
        PricingRule, {"effective_from": {"$gt": start, "$lt": end}}, sort=[("effective_from", 1), ("version", 1)]
    )
    segments: list[tuple[datetime, PricingRule | None]] = [(start, await active_rule(db, start))]
    segments += [(r.effective_from, r) for r in later]
    return segments


async def rate_deployment(db: Session, dep: Deployment, now: datetime) -> list[Charge]:
    """Rate [metered_until, now) for one deployment and settle it. Does not commit; raises on a lost race."""
    start = dep.metered_until or dep.created_at
    events = await db.find(
        DeploymentEvent, {"deployment_id": dep.id, "to_status": {"$ne": None}}, sort=[("created_at", 1)]
    )
    intervals = ready_intervals(events, now, dep.node_id)
    customer = await db.get(Customer, dep.customer_id)
    customer_user = customer.user_id if customer else None
    charges: list[Charge] = []
    segments = await _rules_in(db, start, now)
    for i, (seg_start, rule) in enumerate(segments):
        seg_end = segments[i + 1][0] if i + 1 < len(segments) else now
        if rule is None or customer_user is None:
            continue  # no price in force: usage is measured but free
        seconds = _clip(intervals, seg_start, seg_end)
        tokens = await _tokens(db, dep.id, seg_start, seg_end)
        for node_id in set(seconds) | set(tokens):
            ready_s = seconds.get(node_id, 0.0)
            tin, tout = tokens.get(node_id, (0, 0))
            cpu, ram, vram = await _reservation(db, dep.id, node_id)
            resource, token_amt, amount, provider_amt, fee = price(rule, ready_s, cpu, ram, vram, tin, tout)
            if amount <= 0:
                continue
            customer_wallet = await ledger_service.wallet_for_user(db, customer_user)
            provider_user = await _provider_user(db, node_id)
            provider_wallet = await ledger_service.wallet_for_user(db, provider_user) if provider_user else None
            charge = Charge(
                id=uuid.uuid4(),
                deployment_id=dep.id,
                node_id=node_id,
                customer_wallet_id=customer_wallet.id,
                provider_wallet_id=provider_wallet.id if provider_wallet else None,
                pricing_rule_id=rule.id,
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
                provider_amount=provider_amt if provider_wallet else money(0),
                platform_fee=fee if provider_wallet else amount,
                currency=rule.currency,
            )
            db.add(charge)
            await db.flush()
            await _settle_charge(db, charge, customer_wallet, provider_wallet)
            charges.append(charge)
    moved = await db.update_one(
        Deployment, {"_id": dep.id, "metered_until": dep.metered_until}, {"$set": {"metered_until": now}}
    )
    if not moved:
        raise RuntimeError(f"Billing watermark for deployment {dep.id} moved concurrently")
    dep.metered_until = now
    return charges


async def _settle_charge(db: Session, charge: Charge, customer_wallet, provider_wallet) -> None:
    key = f"charge:{charge.id}"
    period = f"{charge.period_start:%Y-%m-%d %H:%M}-{charge.period_end:%H:%M} UTC"
    await ledger_service.post(
        db,
        key=f"{key}:debit",
        type=TransactionType.COMPUTE_CHARGE,
        amount=charge.amount,
        from_wallet=customer_wallet,
        reference=key,
        deployment_id=charge.deployment_id,
        description=f"Deployment usage {period}",
    )
    if provider_wallet is not None and charge.provider_amount > 0:
        await ledger_service.post(
            db,
            key=f"{key}:provider",
            type=TransactionType.PROVIDER_CREDIT,
            amount=charge.provider_amount,
            to_wallet=provider_wallet,
            reference=key,
            deployment_id=charge.deployment_id,
            description=f"Hosting {period}",
        )
    await ledger_service.post(
        db,
        key=f"{key}:fee",
        type=TransactionType.PLATFORM_FEE,
        amount=charge.platform_fee,
        reference=key,
        deployment_id=charge.deployment_id,
        description="Platform fee",
    )


async def _stop_if_exhausted(db: Session, customer_wallet_id: uuid.UUID) -> int:
    """Stop a customer's running deployments once their prepaid balance is used up."""
    from app.documents.wallet import Wallet
    from app.services import deployment_lifecycle as lifecycle
    from app.services.deployment_service import _stop

    wallet = await db.get(Wallet, customer_wallet_id)
    remaining = await ledger_service.balance(db, customer_wallet_id)  # balances move atomically, not in memory
    if wallet is None or remaining > 0:
        return 0
    customer = await db.find_one(Customer, {"user_id": wallet.user_id})
    if customer is None:
        return 0
    deps = await db.find(
        Deployment,
        {"customer_id": customer.id, "status": {"$in": [s.value for s in lifecycle.ACTIVE if s != S.STOPPING]}},
    )
    for dep in deps:
        await _stop(db, dep, actor="system", message="Stopped: the wallet balance is used up. Top up to deploy again.")
        dep.error_code = "INSUFFICIENT_FUNDS"
        dep.error_message = "The wallet balance is used up"
        audit_service.record(
            db,
            actor_id=None,
            action="deployment.stopped_insufficient_funds",
            resource_type="deployment",
            resource_id=dep.id,
            details={"balance": str(money(remaining))},
        )
    return len(deps)


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
    interval = timedelta(seconds=settings.BILLING_INTERVAL_SECONDS)
    return [d for d in rows if d.ended_at is not None or now - (d.metered_until or d.created_at) >= interval]


async def run_billing(now: datetime | None = None) -> int:
    """Rate every deployment that is due. Each deployment is its own transaction. Returns charges created."""
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
                charges = await rate_deployment(db, dep, now)
                for wallet_id in {c.customer_wallet_id for c in charges}:
                    await _stop_if_exhausted(db, wallet_id)
                await db.commit()
                created += len(charges)
            except Exception:  # noqa: BLE001 - one bad deployment must not stop billing for the rest
                await db.rollback()
                logger.exception("Billing failed for deployment %s", dep_id)
    return created
