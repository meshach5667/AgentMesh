"""Per-machine prices set by providers, and the rates a deployment is placed and estimated at.

Each machine has its own price list (NodePrice versions, each in a currency the provider chose; the newest whose
effective_from has passed is in force). A machine without one is free to use. AgentMesh processes no payments:
customers pay providers directly, and these prices only drive placement and cost estimates.

Customers are protected two ways:

* Placement picks the cheapest machine that fits, within the deployment's price limits (in its currency: per
  hour of its reservation and per million tokens). A machine priced in another currency is not comparable, so it
  is used only if it is free. When a node fails and the customer set no limit, the replacement may not cost more
  than the placement it replaces (a dearer one needs the customer's approval).
* A deployment is never estimated above the rates in force when it was placed on its machine: the reservation keeps
  that snapshot and each estimated rate is the lower of the snapshot and the machine's current price, so a
  provider's increase applies to new placements only, and a decrease applies at once.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.billing import NodePrice
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
    """Unit prices a machine charges, in ``currency``."""

    cpu_core_hour: Decimal
    ram_gb_hour: Decimal
    vram_gb_hour: Decimal
    input_tokens_per_million: Decimal
    output_tokens_per_million: Decimal
    currency: str
    node_price_id: uuid.UUID | None = None

    @classmethod
    def of(cls, doc: NodePrice) -> "Rates":
        return cls(
            cpu_core_hour=Decimal(str(doc.cpu_core_hour)),
            ram_gb_hour=Decimal(str(doc.ram_gb_hour)),
            vram_gb_hour=Decimal(str(doc.vram_gb_hour)),
            input_tokens_per_million=Decimal(str(doc.input_tokens_per_million)),
            output_tokens_per_million=Decimal(str(doc.output_tokens_per_million)),
            currency=doc.currency,
            node_price_id=doc.id,
        )

    @classmethod
    def from_snapshot(cls, snap: dict[str, str]) -> "Rates":
        def d(f: str) -> Decimal:
            return Decimal(snap.get(f, "0"))

        return cls(
            cpu_core_hour=d("cpu_core_hour"),
            ram_gb_hour=d("ram_gb_hour"),
            vram_gb_hour=d("vram_gb_hour"),
            input_tokens_per_million=d("input_tokens_per_million"),
            output_tokens_per_million=d("output_tokens_per_million"),
            currency=snap.get("currency") or settings.DEFAULT_CURRENCY,
        )

    @classmethod
    def free(cls, currency: str | None = None) -> "Rates":
        zero = Decimal(0)
        return cls(zero, zero, zero, zero, zero, currency=currency or settings.DEFAULT_CURRENCY)

    def snapshot(self) -> dict[str, str]:
        return {f: str(getattr(self, f)) for f in PRICE_FIELDS} | {"currency": self.currency}

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
        """These rates, each lowered to ``ceiling`` where that is cheaper (same currency only)."""
        if ceiling.currency != self.currency:
            return self
        return Rates(
            **{f: min(getattr(self, f), getattr(ceiling, f)) for f in PRICE_FIELDS},
            currency=self.currency,
            node_price_id=self.node_price_id,
        )


# --- Lookups -----------------------------------------------------------------------------------------------


async def node_price_at(db: Session, node_id: uuid.UUID, at: datetime | None = None) -> NodePrice | None:
    return await db.find_one(
        NodePrice,
        {"node_id": node_id, "effective_from": {"$lte": at or utcnow()}},
        sort=[("effective_from", -1), ("version", -1)],
    )


async def rates_at(db: Session, node_ids: list[uuid.UUID], at: datetime | None = None) -> dict[uuid.UUID, Rates | None]:
    """What each machine charges at ``at``: its price version in force, or None (free)."""
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
    return {n: Rates.of(own[n]) if n in own else None for n in node_ids}


async def node_price_changes(db: Session, node_id: uuid.UUID, start: datetime, end: datetime) -> list[datetime]:
    rows = await db.find(NodePrice, {"node_id": node_id, "effective_from": {"$gt": start, "$lt": end}})
    return [r.effective_from for r in rows]


async def estimated_rates(
    db: Session, node_id: uuid.UUID, placed_at: dict[str, str] | None, at: datetime
) -> Rates | None:
    """Rates to estimate time ``at`` on a machine at: its price in force then, never above the placement snapshot.
    None: free."""
    own = await node_price_at(db, node_id, at)
    if own is None:
        return None
    rates = Rates.of(own)
    if placed_at is not None:
        placed = Rates.from_snapshot(placed_at)
        if placed.is_free():
            return None  # placed while free: stays free there
        rates = rates.at_most(placed)
    return rates


# --- Price limits ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PriceLimits:
    """What placement may pick. Prices in another currency than ``currency`` are not comparable: such machines are
    allowed only when free. A limit of None means no limit."""

    currency: str
    hourly: Decimal | None = None
    tokens: Decimal | None = None

    def allows(self, rates: Rates | None, cpu_cores: int, ram_mb: int, vram_mb: int) -> bool:
        if rates is None or rates.is_free():
            return True
        if rates.currency != self.currency:
            return False
        if self.hourly is not None and rates.hourly(cpu_cores, ram_mb, vram_mb) > self.hourly:
            return False
        return self.tokens is None or rates.token_price <= self.tokens


def limits_for(
    currency: str | None,
    max_hourly: Decimal | None,
    max_tokens: Decimal | None,
    *,
    replacing: Rates | None = None,
    cpu_cores: int = 0,
    ram_mb: int = 0,
    vram_mb: int = 0,
) -> PriceLimits:
    """The customer's limits. When ``replacing`` a failed placement, a limit the customer did not set is the price
    of the placement being replaced, so recovery never silently costs more."""
    cur = currency or settings.DEFAULT_CURRENCY
    hourly = Decimal(str(max_hourly)) if max_hourly is not None else None
    tokens = Decimal(str(max_tokens)) if max_tokens is not None else None
    if replacing is not None:
        if replacing.is_free():
            hourly = Decimal(0) if hourly is None else hourly
            tokens = Decimal(0) if tokens is None else tokens
        elif replacing.currency == cur:
            hourly = replacing.hourly(cpu_cores, ram_mb, vram_mb) if hourly is None else hourly
            tokens = replacing.token_price if tokens is None else tokens
    return PriceLimits(cur, hourly, tokens)


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
        currency=str(prices.get("currency") or settings.DEFAULT_CURRENCY),
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
        details={"version": price.version, "currency": price.currency, **{f: str(prices[f]) for f in PRICE_FIELDS}},
    )
    return price


async def set_node_price(db: Session, node: Node, prices: dict, actor: User) -> NodePrice:
    """Publish a new price version for a machine, in force at once for new placements. Deployments already on it
    are never estimated above what they were placed at."""
    if node.status in BLOCKED_NODE_STATUSES:
        raise HTTPException(status_code=409, detail="This node is revoked or suspended")
    price = await _add_version(db, node, prices, actor.id)
    await db.commit()
    await db.refresh(price)
    return price


async def set_provider_default(db: Session, provider: Provider, prices: dict, apply_to_existing: bool, actor: User):
    """Set the prices new machines start with; optionally publish them on every active machine too."""
    provider.default_prices = {f: str(prices[f]) for f in PRICE_FIELDS} | {"currency": prices["currency"]}
    db.add(provider)
    updated = 0
    if apply_to_existing:
        nodes = await db.find(Node, {"owner_id": provider.id, "status": {"$nin": list(BLOCKED_NODE_STATUSES)}})
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
    return {f: getattr(rates, f) for f in PRICE_FIELDS} | {"currency": rates.currency}


async def node_pricing(db: Session, node: Node) -> dict:
    charging = (await rates_at(db, [node.id]))[node.id]
    history = await db.find(NodePrice, {"node_id": node.id}, sort=[("version", -1)], limit=50)
    return {"node_id": node.id, "charging": rates_out(charging), "history": history}


async def market(db: Session) -> dict:
    """Price ranges per currency across machines that can take work now. Aggregates only: no machine is named."""
    from app.services.scheduler_service import schedulable

    now = utcnow()
    nodes = [n for n in await db.find(Node, {"mode": {"$ne": None}}) if schedulable(n, now)]
    rates = await rates_at(db, [n.id for n in nodes], now)
    by_currency: dict[str, list[Rates]] = {}
    for r in rates.values():
        if r is not None and not r.is_free():
            by_currency.setdefault(r.currency, []).append(r)
    return {
        "nodes": len(nodes),
        "free_nodes": sum(1 for r in rates.values() if r is None or r.is_free()),
        "currencies": [
            {
                "currency": cur,
                "nodes": len(rs),
                "ranges": {
                    f: {"min": min(getattr(r, f) for r in rs), "max": max(getattr(r, f) for r in rs)}
                    for f in PRICE_FIELDS
                },
            }
            for cur, rs in sorted(by_currency.items())
        ],
    }
