"""Centralized node selection and capacity reservation, for first placements and for moves after a failure.

Eligibility is decided from evidence, never from a node record existing: the node must be ONLINE with a recent
heartbeat (newer than HEARTBEAT_DEGRADED_SECONDS), have completed its recovery heartbeats after an outage, not be in a
failure cooldown, accept work (provider and worker both), and have the free capacity, runtime, hardware, region and
provider the deployment requires. Price limits come last. Among eligible nodes the ranking is deterministic:
cheapest first, then the most free memory, then reputation, then node id. Sponsorships play no part.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from app.core.config import settings
from app.core.database import Session
from app.core.timeutil import utcnow
from app.documents.node import Node, NodeStatus
from app.documents.reservation import ResourceReservation
from app.services import credit_service
from app.services.catalog_service import ResourceRequest
from app.services.node_pricing_service import PriceLimits, Rates, rates_at

# Reasons a node was rejected, reported back to the customer in aggregate (never per node).
REASON_UNAVAILABLE = "provider_unavailable"  # offline, stale heartbeat, paused, or suspended
REASON_RUNTIME = "unsupported_runtime"
REASON_HARDWARE = "incompatible_hardware"  # e.g. GPU required but none allocated
REASON_CAPACITY = "insufficient_capacity"
REASON_REGION = "region_mismatch"
REASON_PREVIOUSLY_FAILED = "previously_failed"  # nodes this deployment already failed on
REASON_COMMUNITY = "community_not_accepted"  # provider has not opted in to unreviewed community models
REASON_PRICE = "over_price_limit"  # the node charges more than the deployment's price limits
REASON_CURRENCY = "other_currency"  # priced in a currency other than the deployment's, so not comparable
REASON_PROVIDER = "other_provider"  # not run by the provider the deployment is restricted to
REASON_DEGRADED = "node_degraded"  # late heartbeats, recovering from an outage, or repeated recent failures
REASON_NO_CREDIT = "no_prepaid_credit"  # priced machine; the customer lacks enough verified credit with its provider

REASON_TEXT = {
    REASON_UNAVAILABLE: "nodes are offline, paused, or not reporting heartbeats",
    REASON_RUNTIME: "nodes do not offer the required runtime",
    REASON_HARDWARE: "nodes lack the required hardware (for example a GPU)",
    REASON_CAPACITY: "nodes do not have enough free CPU, memory, disk, or VRAM allocated to AgentMesh",
    REASON_REGION: "nodes are outside the requested region",
    REASON_PREVIOUSLY_FAILED: "nodes already failed this deployment",
    REASON_COMMUNITY: "nodes do not accept community models (providers must opt in)",
    REASON_PRICE: "nodes charge more than your price limit (raise max_hourly_price or max_token_price)",
    REASON_CURRENCY: "nodes are priced in another currency",
    REASON_PROVIDER: "nodes belong to other providers than the one you chose",
    REASON_DEGRADED: "nodes are degraded (late heartbeats, recovering, or failing repeatedly)",
    REASON_NO_CREDIT: "nodes need prepaid credit with their provider (buy credit to use them)",
}


@dataclass
class Evaluation:
    eligible: list[Node] = field(default_factory=list)
    reasons: Counter = field(default_factory=Counter)
    rates: dict = field(default_factory=dict)  # node id -> Rates it charges now (None: free)

    def explain(self) -> str:
        if not self.reasons:
            return "No compute nodes are registered."
        parts = [f"{count} {REASON_TEXT[r]}" for r, count in self.reasons.most_common()]
        return "No eligible node: " + "; ".join(parts) + "."


class NoEligibleNode(Exception):  # noqa: N818
    def __init__(self, evaluation: Evaluation):
        self.evaluation = evaluation
        super().__init__(evaluation.explain())


def _free(node: Node, resource: str) -> int:
    return (getattr(node, f"allocated_{resource}") or 0) - (getattr(node, f"reserved_{resource}") or 0)


def node_is_fresh(node: Node, now: datetime | None = None) -> bool:
    """Heartbeat within the timeout: the node counts as connected (it may still be too late for new work)."""
    now = now or utcnow()
    if node.last_heartbeat is None:
        return False
    return now - node.last_heartbeat <= timedelta(seconds=settings.HEARTBEAT_TIMEOUT_SECONDS)


def _degraded(node: Node, now: datetime) -> bool:
    late = node.last_heartbeat is None or now - node.last_heartbeat > timedelta(
        seconds=settings.HEARTBEAT_DEGRADED_SECONDS
    )
    recovering = (node.recovery_heartbeats or 0) < settings.NODE_RECOVERY_HEARTBEATS
    cooling = node.degraded_until is not None and node.degraded_until > now
    return late or recovering or cooling


def schedulable(node: Node, now: datetime | None = None) -> bool:
    """May receive new work now, judged from health evidence (not just because the node exists)."""
    now = now or utcnow()
    return (
        node.status == NodeStatus.ONLINE
        and bool(node.accepting_workloads)
        and bool(node.worker_available)
        and node_is_fresh(node, now)
        and not _degraded(node, now)
    )


def health_state(node: Node, now: datetime | None = None) -> str:
    """ACTIVE, BUSY, DEGRADED, DRAINING or OFFLINE (or the operator's SUSPENDED/QUARANTINED/REVOKED) for display.

    ACTIVE takes work; BUSY runs work and takes more while capacity lasts; DEGRADED gets no new work until its
    heartbeats are timely again, it finishes recovering, or its failure cooldown ends; DRAINING was paused by the
    provider (running work continues); OFFLINE is out of contact and its work is being moved."""
    now = now or utcnow()
    if node.status in (NodeStatus.SUSPENDED, NodeStatus.QUARANTINED, NodeStatus.REVOKED, NodeStatus.REGISTERING):
        return str(node.status.value if isinstance(node.status, NodeStatus) else node.status)
    if node.status == NodeStatus.OFFLINE or not node_is_fresh(node, now):
        return "OFFLINE"
    if not node.accepting_workloads or not node.worker_available:
        return "DRAINING"
    if _degraded(node, now):
        return "DEGRADED"
    if any((getattr(node, f"reserved_{r}") or 0) > 0 for r in ("cpu_cores", "ram_mb", "vram_mb")):
        return "BUSY"
    return "ACTIVE"


def offers_runtime(node: Node, runtime: str) -> bool:
    return any(r.get("name") == runtime and r.get("available") for r in (node.runtimes or []) if isinstance(r, dict))


async def evaluate_nodes(
    db: Session,
    req: ResourceRequest,
    exclude: set | None = None,
    limits: PriceLimits | None = None,
    providers: set | None = None,
    customer_id=None,
) -> Evaluation:
    """Nodes that can take ``req`` within ``limits`` (and of one of ``providers``, if given), cheapest first. With a
    ``customer_id``, priced machines are eligible only while that customer holds enough verified prepaid credit with
    the machine's provider; free machines need none."""
    nodes = await db.find(Node, {"mode": {"$ne": None}})
    ev = Evaluation()
    now = utcnow()
    limits = limits or PriceLimits(settings.DEFAULT_CURRENCY)
    for node in nodes:
        if exclude and node.id in exclude:
            ev.reasons[REASON_PREVIOUSLY_FAILED] += 1
        elif providers is not None and node.owner_id not in providers:
            ev.reasons[REASON_PROVIDER] += 1
        elif (
            node.status != NodeStatus.ONLINE
            or not node.accepting_workloads
            or not node.worker_available
            or not node_is_fresh(node, now)
        ):
            ev.reasons[REASON_UNAVAILABLE] += 1
        elif _degraded(node, now):
            ev.reasons[REASON_DEGRADED] += 1
        elif req.community and not node.accepts_community_models:
            ev.reasons[REASON_COMMUNITY] += 1
        elif req.region and node.region != req.region:
            ev.reasons[REASON_REGION] += 1
        elif not offers_runtime(node, req.runtime):
            ev.reasons[REASON_RUNTIME] += 1
        elif req.gpu_required and (node.allocated_vram_mb or 0) <= 0:
            ev.reasons[REASON_HARDWARE] += 1
        elif (
            _free(node, "cpu_cores") < req.cpu_cores
            or _free(node, "ram_mb") < req.ram_mb
            or _free(node, "disk_mb") < req.disk_mb
            or _free(node, "vram_mb") < req.vram_mb
        ):
            ev.reasons[REASON_CAPACITY] += 1
        else:
            ev.eligible.append(node)
    ev.rates = await rates_at(db, [n.id for n in ev.eligible], now)
    credit = await credit_service.balances_for(db, customer_id) if customer_id is not None else None
    within = []
    for n in ev.eligible:
        rates = ev.rates[n.id]
        if rates is not None and not rates.is_free() and rates.currency != limits.currency:
            ev.reasons[REASON_CURRENCY] += 1
        elif not limits.allows(rates, req.cpu_cores, req.ram_mb, req.vram_mb):
            ev.reasons[REASON_PRICE] += 1
        elif (
            credit is not None
            and rates is not None
            and not rates.is_free()
            and not credit_service.covers(
                credit.get((n.owner_id, rates.currency), Decimal(0)),
                rates.hourly(req.cpu_cores, req.ram_mb, req.vram_mb),
            )
        ):
            ev.reasons[REASON_NO_CREDIT] += 1
        else:
            within.append(n)
    ev.eligible = within

    # Cheapest first (hourly price of this reservation, then token prices; all in the limits' currency or free);
    # among equal prices the node with the most free memory, then reputation, then id, so ties are deterministic.
    def rank(n: Node):
        rates = ev.rates[n.id] or Rates.free()
        tokens = rates.input_tokens_per_million + rates.output_tokens_per_million
        hourly = rates.hourly(req.cpu_cores, req.ram_mb, req.vram_mb)
        return (hourly, tokens, -_free(n, "ram_mb"), -float(n.reputation_score or 0), str(n.id))

    ev.eligible.sort(key=rank)
    return ev


async def try_reserve(
    db: Session, node: Node, deployment_id, req: ResourceRequest, rates: Rates | None = None, standby: bool = False
) -> bool:
    """Atomically reserve capacity on one node. The conditional update only succeeds if the node still has
    room at the moment it executes, so concurrent requests cannot oversubscribe. ``rates`` (what the node charges
    now) is kept with the reservation as the most the deployment will be billed there. Does not commit."""
    wanted = {"cpu_cores": req.cpu_cores, "ram_mb": req.ram_mb, "disk_mb": req.disk_mb, "vram_mb": req.vram_mb}
    conditions: dict = {
        "_id": node.id,
        "status": NodeStatus.ONLINE.value,
        "accepting_workloads": True,
        "worker_available": True,
        "$expr": {
            "$and": [
                {"$lte": [{"$add": [f"$reserved_{r}", amount]}, f"$allocated_{r}"]} for r, amount in wanted.items()
            ]
        },
    }
    if req.community:  # re-checked here so a provider opting out cannot race a reservation
        conditions["accepts_community_models"] = True
    if not await db.update_one(Node, conditions, {"$inc": {f"reserved_{r}": amount for r, amount in wanted.items()}}):
        return False
    db.add(
        ResourceReservation(
            deployment_id=deployment_id,
            node_id=node.id,
            cpu_cores=req.cpu_cores,
            ram_mb=req.ram_mb,
            disk_mb=req.disk_mb,
            vram_mb=req.vram_mb,
            rates=(rates or Rates.free()).snapshot(),
            status="STANDBY" if standby else "ACTIVE",
        )
    )
    return True


async def schedule(
    db: Session,
    deployment_id,
    req: ResourceRequest,
    exclude: set | None = None,
    limits: PriceLimits | None = None,
    providers: set | None = None,
    customer_id=None,
    standby: bool = False,
) -> tuple[Node, Rates | None]:
    """Reserve capacity on the cheapest eligible node; returns it and the rates it charges. A node that fills up
    between evaluation and reservation is skipped for the next one. ``standby`` holds capacity for the target of a
    planned move (see placement_service.start_migration)."""
    ev = await evaluate_nodes(db, req, exclude, limits, providers, customer_id)
    for node in ev.eligible:
        if await try_reserve(db, node, deployment_id, req, ev.rates[node.id], standby):
            return node, ev.rates[node.id]
        ev.reasons[REASON_CAPACITY] += 1  # lost a race for this node's capacity
    raise NoEligibleNode(ev)


async def release_reservation(db: Session, deployment_id) -> bool:
    """Release a deployment's reservation exactly once. Safe to call repeatedly. Does not commit."""
    reservation = await db.find_one(ResourceReservation, {"deployment_id": deployment_id, "status": "ACTIVE"})
    if reservation is None:
        return False
    claimed = await db.update_one(
        ResourceReservation,
        {"_id": reservation.id, "status": "ACTIVE"},
        {"$set": {"status": "RELEASED", "released_at": utcnow()}},
    )
    if not claimed:
        return False
    await db.update_one(
        Node,
        {"_id": reservation.node_id},
        {
            "$inc": {
                "reserved_cpu_cores": -reservation.cpu_cores,
                "reserved_ram_mb": -reservation.ram_mb,
                "reserved_disk_mb": -reservation.disk_mb,
                "reserved_vram_mb": -reservation.vram_mb,
            }
        },
    )
    return True


async def release_standby(db: Session, deployment_id) -> bool:
    """Release capacity held for a planned move that did not complete. Does not commit."""
    reservation = await db.find_one(ResourceReservation, {"deployment_id": deployment_id, "status": "STANDBY"})
    if reservation is None:
        return False
    if not await db.update_one(
        ResourceReservation,
        {"_id": reservation.id, "status": "STANDBY"},
        {"$set": {"status": "RELEASED", "released_at": utcnow()}},
    ):
        return False
    await db.update_one(
        Node,
        {"_id": reservation.node_id},
        {
            "$inc": {
                "reserved_cpu_cores": -reservation.cpu_cores,
                "reserved_ram_mb": -reservation.ram_mb,
                "reserved_disk_mb": -reservation.disk_mb,
                "reserved_vram_mb": -reservation.vram_mb,
            }
        },
    )
    return True
