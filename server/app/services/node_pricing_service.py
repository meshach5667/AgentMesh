"""Per-machine prices set by providers, and the rates a deployment is placed and billed at.

Each node has its own price list (NodePrice versions; the newest whose effective_from has passed is in force). A
node without one charges the network prices, the operator's PricingRule, which also sets the platform commission.

Customers are protected two ways:

* Placement picks the cheapest node that fits, within the deployment's price limits (per hour of its reservation
  and per million tokens). Limits the customer does not set default to the network prices, so a node priced above
  them is only used by customers who raise their limit.
* A deployment is never billed above the rates in force when it was placed on its node: the reservation keeps that
  snapshot, and each billed rate is the lower of the snapshot and the node's current price. A provider's increase
  therefore applies to new placements only; a decrease applies at once.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.billing import NodePrice, PricingRule
from app.documents.node import BLOCKED_NODE_STATUSES, Node
from app.documents.user import Provider, User
from app.services import audit_service

PRICE_FIELDS = (
    "cpu_core_hour",
    "ram_gb_hour",
    "vram_gb_hour",
    "input_tokens_per_million",
    "output_tokens_per_million",
)
MB_PER_GB = Decimal(1024)


@dataclass(frozen=True)
class Rates:
    """Unit prices charged on one node: its own price version (source "node") or the network's ("network")."""

    cpu_core_hour: Decimal
    ram_gb_hour: Decimal
    vram_gb_hour: Decimal
    input_tokens_per_million: Decimal
    output_tokens_per_million: Decimal
    source: str = "network"
    node_price_id: uuid.UUID | None = None

    @classmethod
    def of(cls, doc: NodePrice | PricingRule, source: str) -> "Rates":
        return cls(
            **{f: Decimal(str(getattr(doc, f))) for f in PRICE_FIELDS},
            source=source,
            node_price_id=doc.id if source == "node" else None,
        )

    @classmethod
    def from_snapshot(cls, snap: dict[str, str]) -> "Rates":
        return cls(**{f: Decimal(snap.get(f, "0")) for f in PRICE_FIELDS}, source=snap.get("source", "network"))

    @classmethod
    def free(cls) -> "Rates":
        return cls(*(Decimal(0),) * len(PRICE_FIELDS))

    def snapshot(self) -> dict[str, str]:
        return {f: str(getattr(self, f)) for f in PRICE_FIELDS} | {"source": self.source}

    def hourly(self, cpu_cores: int, ram_mb: int, vram_mb: int) -> Decimal:
        return (
            self.cpu_core_hour * cpu_cores
            + self.ram_gb_hour * Decimal(ram_mb) / MB_PER_GB
            + self.vram_gb_hour * Decimal(vram_mb) / MB_PER_GB
        )

    @property
    def token_price(self) -> Decimal:
        """The higher of the input and output price per million tokens (what the token limit is compared to)."""
        return max(self.input_tokens_per_million, self.output_tokens_per_million)

    def is_free(self) -> bool:
        return not any(getattr(self, f) for f in PRICE_FIELDS)

    def at_most(self, ceiling: "Rates") -> "Rates":
        """These rates, each lowered to ``ceiling`` where that is cheaper."""
        return Rates(
            **{f: min(getattr(self, f), getattr(ceiling, f)) for f in PRICE_FIELDS},
            source=self.source,
            node_price_id=self.node_price_id,
        )


# --- Lookups -----------------------------------------------------------------------------------------------


async def network_rule(db: Session, at: datetime | None = None) -> PricingRule | None:
    """The network price version in force at ``at`` (now by default)."""
    at = at or utcnow()
    return await db.find_one(
        PricingRule, {"effective_from": {"$lte": at}}, sort=[("effective_from", -1), ("version", -1)]
    )


async def node_price_at(db: Session, node_id: uuid.UUID, at: datetime | None = None) -> NodePrice | None:
    return await db.find_one(
        NodePrice,
        {"node_id": node_id, "effective_from": {"$lte": at or utcnow()}},
        sort=[("effective_from", -1), ("version", -1)],
    )


async def rates_at(db: Session, node_ids: list[uuid.UUID], at: datetime | None = None) -> dict[uuid.UUID, Rates | None]:
    """What each node charges at ``at``: its own price version, else the network prices, else None (free)."""
    at = at or utcnow()
    own: dict[uuid.UUID, NodePrice] = {}
    if node_ids:
        rows = await db.find(
            NodePrice,
            {"node_id": {"$in": list(node_ids)}, "effective_from": {"$lte": at}},
            sort=[("effective_from", -1), ("version", -1)],
        )
        for row in rows:
            own.setdefault(row.node_id, row)
    rule = await network_rule(db, at)
    network = Rates.of(rule, "network") if rule else None
    return {n: Rates.of(own[n], "node") if n in own else network for n in node_ids}


async def node_price_changes(db: Session, node_id: uuid.UUID, start: datetime, end: datetime) -> list[datetime]:
    rows = await db.find(NodePrice, {"node_id": node_id, "effective_from": {"$gt": start, "$lt": end}})
    return [r.effective_from for r in rows]


async def billed_rates(
    db: Session, node_id: uuid.UUID, placed_at: dict[str, str] | None, at: datetime
) -> tuple[Rates | None, PricingRule | None]:
    """(rates to bill, network version for the commission) for time ``at`` on a node. A node with its own price
    is billed at most at the placement snapshot ``placed_at``; network prices apply as the operator sets them."""
    rule = await network_rule(db, at)
    own = await node_price_at(db, node_id, at)
    if own is None:
        return (Rates.of(rule, "network") if rule else None), rule
    rates = Rates.of(own, "node")
    if placed_at is not None:
        rates = rates.at_most(Rates.from_snapshot(placed_at))
    return rates, rule


# --- Price limits ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PriceLimits:
    hourly: Decimal | None  # per hour of the reservation; None: no limit
    tokens: Decimal | None  # per million tokens, input or output; None: no limit

    def allows(self, rates: Rates | None, cpu_cores: int, ram_mb: int, vram_mb: int) -> bool:
        rates = rates or Rates.free()
        if self.hourly is not None and rates.hourly(cpu_cores, ram_mb, vram_mb) > self.hourly:
            return False
        return self.tokens is None or rates.token_price <= self.tokens


async def limits_for(
    db: Session, max_hourly: Decimal | None, max_tokens: Decimal | None, cpu_cores: int, ram_mb: int, vram_mb: int
) -> PriceLimits:
    """The customer's limits, with the network prices standing in for any they did not set."""
    if max_hourly is not None and max_tokens is not None:
        return PriceLimits(Decimal(str(max_hourly)), Decimal(str(max_tokens)))
    rule = await network_rule(db)
    network = Rates.of(rule, "network") if rule else None
    return PriceLimits(
        Decimal(str(max_hourly))
        if max_hourly is not None
        else (network.hourly(cpu_cores, ram_mb, vram_mb) if network else None),
        Decimal(str(max_tokens)) if max_tokens is not None else (network.token_price if network else None),
    )


# --- Changes by providers ----------------------------------------------------------------------------------


async def provider_for(db: Session, user: User) -> Provider:
    provider = await db.find_one(Provider, {"user_id": user.id})
    if provider is None:
        raise HTTPException(status_code=403, detail="Provider account required")
    return provider


async def _add_version(db: Session, node: Node, prices: dict, actor_id: uuid.UUID | None) -> NodePrice:
    newest = await db.find_one(NodePrice, {"node_id": node.id}, sort=[("version", -1)])
    price = NodePrice(
        id=uuid.uuid4(),
        node_id=node.id,
        provider_id=node.owner_id,
        version=(newest.version if newest else 0) + 1,
        currency=settings.BILLING_CURRENCY,
        effective_from=utcnow(),
        created_by=actor_id,
        **{f: Decimal(str(prices[f])) for f in PRICE_FIELDS},
    )
    db.add(price)
    audit_service.record(
        db,
        actor_id=actor_id,
        action="node.price_set",
        resource_type="node",
        resource_id=node.id,
        details={"version": price.version, **{f: str(prices[f]) for f in PRICE_FIELDS}},
    )
    return price


async def set_node_price(db: Session, node: Node, prices: dict, actor: User) -> NodePrice:
    """Publish a new price version for a node, in force at once. Deployments already on the node keep paying at
    most what they were placed at."""
    if node.status in BLOCKED_NODE_STATUSES:
        raise HTTPException(status_code=409, detail="This node is revoked or suspended")
    price = await _add_version(db, node, prices, actor.id)
    await db.commit()
    await db.refresh(price)
    return price


async def set_provider_default(db: Session, provider: Provider, prices: dict, apply_to_existing: bool, actor: User):
    """Set the prices new machines start with; optionally publish them on every active machine too."""
    provider.default_prices = {f: str(prices[f]) for f in PRICE_FIELDS}
    db.add(provider)
    updated = 0
    if apply_to_existing:
        nodes = await db.find(
            Node, {"owner_id": provider.id, "status": {"$nin": list(BLOCKED_NODE_STATUSES)}}
        )
        for node in nodes:
            await _add_version(db, node, prices, actor.id)
            updated += 1
    await db.commit()
    return updated


async def apply_provider_default(db: Session, node: Node) -> None:
    """Give a newly enrolled machine its provider's default prices, if they set any. Does not commit."""
    provider = await db.get(Provider, node.owner_id)
    if provider is not None and provider.default_prices:
        await _add_version(db, node, provider.default_prices, None)


# --- Views -------------------------------------------------------------------------------------------------


def rates_out(rates: Rates | None) -> dict | None:
    if rates is None:
        return None
    return {f: getattr(rates, f) for f in PRICE_FIELDS} | {"source": rates.source}


def commission_rate(rule: PricingRule | None) -> Decimal:
    return Decimal(str(rule.platform_fee_rate)) if rule else settings.DEFAULT_PLATFORM_FEE_RATE


async def node_pricing(db: Session, node: Node) -> dict:
    rule = await network_rule(db)
    charging = (await rates_at(db, [node.id]))[node.id]
    history = await db.find(NodePrice, {"node_id": node.id}, sort=[("version", -1)], limit=50)
    return {
        "node_id": node.id,
        "currency": settings.BILLING_CURRENCY,
        "charging": rates_out(charging),
        "network": rates_out(Rates.of(rule, "network") if rule else None),
        "commission_rate": commission_rate(rule),
        "history": history,
    }


async def market(db: Session) -> dict:
    """Price ranges across machines that can take work now. Aggregates only: no node is identified."""
    from app.documents.node import NodeStatus
    from app.services.scheduler_service import node_is_fresh

    nodes = await db.find(
        Node, {"status": NodeStatus.ONLINE.value, "accepting_workloads": True, "worker_available": True}
    )
    nodes = [n for n in nodes if node_is_fresh(n)]
    rates = await rates_at(db, [n.id for n in nodes])
    priced = [r or Rates.free() for r in rates.values()]
    rule = await network_rule(db)
    return {
        "currency": settings.BILLING_CURRENCY,
        "nodes": len(nodes),
        "own_prices": sum(1 for r in rates.values() if r is not None and r.source == "node"),
        "ranges": {
            f: {"min": min(getattr(r, f) for r in priced), "max": max(getattr(r, f) for r in priced)}
            for f in PRICE_FIELDS
        }
        if priced
        else {},
        "network": rates_out(Rates.of(rule, "network") if rule else None),
        "commission_rate": commission_rate(rule),
    }
