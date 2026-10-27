"""Pricing and rating: turns measured usage into charges and ledger postings.

What is charged, per deployment and node, at that node's rates (its provider's own prices, else the network
prices; never above the rates it was placed at, see node_pricing_service):

* READY time x reserved resources (CPU cores, RAM, VRAM). READY intervals come from the control plane's own
  lifecycle events, not from the worker. UNHEALTHY time is not charged.
* Input/output tokens at the per-million prices, for successful requests only. Counts are runtime-reported (see
  UsageRecord.token_source); requests without counts are not charged for tokens.

Each charge is split by the platform commission of the network pricing version in force
(settings.DEFAULT_PLATFORM_FEE_RATE, 10%, unless the operator set another): the fee is rounded to the ledger's
precision and the provider is credited exactly the rest, so fee + provider share always equals what the customer
paid.

A background job rates each deployment's window [metered_until, now) at most every BILLING_INTERVAL_SECONDS,
splitting at network and node price changes and at node changes. Each (deployment, node, period_start) produces at most
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
from app.services.node_pricing_service import PRICE_FIELDS, Rates, billed_rates, network_rule, node_price_changes

logger = logging.getLogger(__name__)

SECONDS_PER_HOUR = Decimal(3600)
MILLION = Decimal(1_000_000)


# --- Pricing rules -----------------------------------------------------------------------------------------


active_rule = network_rule


async def list_rules(db: Session) -> list[PricingRule]:
    return await db.find(PricingRule, sort=[("version", -1)])


async def create_rule(db: Session, data: dict, actor: User) -> PricingRule:
    """Add a new pricing version. Versions are immutable and cannot take effect in the past, so charges
    already rated are never re-priced. Without a ``platform_fee_rate`` it gets settings.DEFAULT_PLATFORM_FEE_RATE."""
    now = utcnow()
    if data.get("platform_fee_rate") is None:
        data["platform_fee_rate"] = settings.DEFAULT_PLATFORM_FEE_RATE
    if not 0 <= data["platform_fee_rate"] <= settings.MAX_PLATFORM_FEE_RATE:
        raise HTTPException(
            status_code=422,
            detail=f"platform_fee_rate must be between 0 and {settings.MAX_PLATFORM_FEE_RATE} on this network",
        )
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


RULE_PRICES = PRICE_FIELDS


async def change_commission(
    db: Session, rate: Decimal, effective_from: datetime | None, notes: str | None, actor: User
) -> PricingRule:
    """Publish a version with the prices in force and a new commission rate. Refused while a later version is
    scheduled (it would keep its own rate, which is easy to miss): publish a full version instead."""
    current = await active_rule(db)
    if current is None:
        raise HTTPException(status_code=409, detail="No prices are in force yet; publish a full price version first")
    if await db.count(PricingRule, {"effective_from": {"$gt": utcnow()}}):
        raise HTTPException(
            status_code=409, detail="A later price version is already scheduled; publish a full version instead"
        )
    data: dict = {k: getattr(current, k) for k in RULE_PRICES}
    data |= {
        "platform_fee_rate": rate,
        "effective_from": effective_from,
        "notes": notes or f"Commission {current.platform_fee_rate} -> {rate} (prices of version {current.version})",
    }
    return await create_rule(db, data, actor)


def split(amount: Decimal, rate: Decimal) -> tuple[Decimal, Decimal]:
    """(provider share, platform fee) of a charge. The fee is rounded; the provider gets exactly the rest."""
    fee = money(amount * Decimal(rate))
    return amount - fee, fee


async def require_prepaid(
    db: Session, user_id: uuid.UUID, rates: Rates | None, cpu_cores: int, ram_mb: int, vram_mb: int
) -> None:
    """Refuse a deployment the customer cannot afford for BILLING_MIN_PREPAID_HOURS of its reservation at the
    rates of the node it was placed on."""
    if rates is None or rates.is_free():
        return
    hours = Decimal(str(settings.BILLING_MIN_PREPAID_HOURS))
    needed = money(rates.hourly(cpu_cores, ram_mb, vram_mb) * hours)
    wallet = await ledger_service.wallet_for_user(db, user_id)
    have = await ledger_service.balance(db, wallet.id)
    if have < needed or have <= 0:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "insufficient_balance",
                "message": f"This deployment needs at least {needed} {settings.BILLING_CURRENCY} in your wallet "
                f"({settings.BILLING_MIN_PREPAID_HOURS:g} h of its reserved resources); you have {money(have)}.",
                "required": str(needed),
                "balance": str(money(have)),
                "currency": settings.BILLING_CURRENCY,
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
                    "outcome": "success",  # failed, cancelled or timed-out requests are not billed
                    "created_at": {"$gte": start, "$lt": end},
                }
            },
            {
                "$group": {
                    "_id": "$node_id",
                    # Input tokens likewise: at most the forwarded request's bytes plus the runtime's chat template.
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


async def placement_rates(db: Session, res: ResourceReservation | None) -> dict[str, str] | None:
    """The most a deployment pays on a node: the rates kept with its reservation. Reservations made before rates
    were kept fall back to the network prices of their time."""
    if res is None:
        return None
    if res.rates is not None:
        return res.rates
    rule = await network_rule(db, res.created_at)
    return (Rates.of(rule, "network") if rule else Rates.free()).snapshot()


async def _provider_user(db: Session, node_id: uuid.UUID | None) -> uuid.UUID | None:
    if node_id is None:
        return None
    node = await db.get(Node, node_id)
    provider = await db.get(Provider, node.owner_id) if node else None
    return provider.user_id if provider else None


# --- Rating ------------------------------------------------------------------------------------------------


def price(rates: Rates, fee_rate, ready_seconds: float, cpu: int, ram_mb: int, vram_mb: int, tin: int, tout: int):
    hours = Decimal(str(ready_seconds)) / SECONDS_PER_HOUR
    resource = money(rates.hourly(cpu, ram_mb, vram_mb) * hours)
    tokens = money((rates.input_tokens_per_million * tin + rates.output_tokens_per_million * tout) / MILLION)
    amount = resource + tokens
    provider_amount, fee = split(amount, fee_rate)
    return resource, tokens, amount, provider_amount, fee


async def _cuts(db: Session, node_id: uuid.UUID | None, start: datetime, end: datetime) -> list[datetime]:
    """Boundaries of [start, end) where the network prices or this node's own prices change."""
    rules = await db.find(PricingRule, {"effective_from": {"$gt": start, "$lt": end}})
    points = {start, end, *(r.effective_from for r in rules)}
    if node_id is not None:
        points.update(await node_price_changes(db, node_id, start, end))
    return sorted(points)


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
    whole = _clip(intervals, start, now)
    token_nodes = await _tokens(db, dep.id, start, now)
    for node_id in set(whole) | set(token_nodes):
        if customer_user is None:
            break
        reservation = await _reservation(db, dep.id, node_id)
        cpu, ram, vram = (reservation.cpu_cores, reservation.ram_mb, reservation.vram_mb) if reservation else (0, 0, 0)
        placed_at = await placement_rates(db, reservation)
        cuts = await _cuts(db, node_id, start, now)
        for seg_start, seg_end in zip(cuts, cuts[1:], strict=False):
            if node_id is not None:
                rates, rule = await billed_rates(db, node_id, placed_at, seg_start)
            else:
                rule = await active_rule(db, seg_start)
                rates = Rates.of(rule, "network") if rule else None
            if rates is None:
                continue  # no price in force: usage is measured but free
            ready_s = _clip(intervals, seg_start, seg_end).get(node_id, 0.0)
            tin, tout = (await _tokens(db, dep.id, seg_start, seg_end)).get(node_id, (0, 0))
            fee_rate = rule.platform_fee_rate if rule else settings.DEFAULT_PLATFORM_FEE_RATE
            resource, token_amt, amount, provider_amt, fee = price(rates, fee_rate, ready_s, cpu, ram, vram, tin, tout)
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
                pricing_rule_id=rule.id if rule else None,
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
                provider_amount=provider_amt if provider_wallet else money(0),
                platform_fee=fee if provider_wallet else amount,
                platform_fee_rate=fee_rate,
                currency=settings.BILLING_CURRENCY,
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


# --- Summaries ---------------------------------------------------------------------------------------------


async def charge_totals(db: Session, match: dict) -> dict:
    """Totals of the charges matching ``match``: gross, platform fee and provider share, by resources and tokens."""
    rows = await db.aggregate(
        Charge,
        [
            {"$match": match},
            {
                "$group": {
                    "_id": None,
                    "charges": {"$sum": 1},
                    **{f: {"$sum": f"${f}"} for f in ("amount", "platform_fee", "provider_amount")},
                    **{f: {"$sum": f"${f}"} for f in ("resource_amount", "token_amount")},
                }
            },
        ],
    )
    row = rows[0] if rows else {}
    gross = money(row.get("amount") or 0)
    fee = money(row.get("platform_fee") or 0)
    return {
        "charges": int(row.get("charges") or 0),
        "gross": gross,
        "platform_fee": fee,
        "provider_share": money(row.get("provider_amount") or 0),
        "resource_amount": money(row.get("resource_amount") or 0),
        "token_amount": money(row.get("token_amount") or 0),
        "effective_fee_rate": (fee / gross).quantize(Decimal("0.0001")) if gross else None,
    }


async def summary(db: Session, user: User, scope: str, days: int) -> dict:
    """What the caller paid ("customer"), earned ("provider"), or the whole network's compute revenue ("network",
    staff only, checked by the caller) over the last ``days`` days."""
    since = utcnow() - timedelta(days=days)
    match: dict = {"created_at": {"$gte": since}}
    if scope != "network":
        wallet = await ledger_service.wallet_for_user(db, user.id)
        match["customer_wallet_id" if scope == "customer" else "provider_wallet_id"] = wallet.id
    return {
        "scope": scope,
        "days": days,
        "since": since,
        "currency": settings.BILLING_CURRENCY,
        "totals": await charge_totals(db, match),
    }
