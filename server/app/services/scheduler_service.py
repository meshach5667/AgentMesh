"""Resource-aware node selection and capacity reservation."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.db_utils import rowcount as _rowcount
from app.models.node import Node, NodeHardware, NodeStatus
from app.models.reservation import ResourceReservation
from app.services.catalog_service import ResourceRequest

# Reasons a node was rejected, reported back to the customer in aggregate (never per node).
REASON_UNAVAILABLE = "provider_unavailable"  # offline, stale heartbeat, paused, or suspended
REASON_RUNTIME = "unsupported_runtime"
REASON_HARDWARE = "incompatible_hardware"  # e.g. GPU required but none allocated
REASON_CAPACITY = "insufficient_capacity"
REASON_REGION = "region_mismatch"

REASON_TEXT = {
    REASON_UNAVAILABLE: "nodes are offline, paused, or not reporting heartbeats",
    REASON_RUNTIME: "nodes do not offer the required runtime",
    REASON_HARDWARE: "nodes lack the required hardware (for example a GPU)",
    REASON_CAPACITY: "nodes do not have enough free CPU, memory, disk, or VRAM allocated to AgentMesh",
    REASON_REGION: "nodes are outside the requested region",
}


@dataclass
class Evaluation:
    eligible: list[Node] = field(default_factory=list)
    reasons: Counter = field(default_factory=Counter)

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
    now = now or datetime.utcnow()
    return bool(node.last_heartbeat) and now - node.last_heartbeat <= timedelta(
        seconds=settings.HEARTBEAT_TIMEOUT_SECONDS
    )


def offers_runtime(node: Node, runtime: str) -> bool:
    return any(r.get("name") == runtime and r.get("available") for r in (node.runtimes or []) if isinstance(r, dict))


async def evaluate_nodes(db: AsyncSession, req: ResourceRequest) -> Evaluation:
    result = await db.execute(select(Node).where(Node.mode.is_not(None)))
    nodes = list(result.scalars().all())
    ev = Evaluation()
    now = datetime.utcnow()
    for node in nodes:
        if node.status != NodeStatus.ONLINE or not node.accepting_workloads or not node_is_fresh(node, now):
            ev.reasons[REASON_UNAVAILABLE] += 1
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
    # Prefer the node with the most free memory, then reputation. Spreads load across providers.
    ev.eligible.sort(key=lambda n: (_free(n, "ram_mb"), float(n.reputation_score or 0)), reverse=True)
    return ev


async def try_reserve(db: AsyncSession, node: Node, deployment_id, req: ResourceRequest) -> bool:
    """Atomically reserve capacity on one node. The conditional UPDATE only succeeds if the node still has
    room at the moment it executes, so concurrent requests cannot oversubscribe. Does not commit."""
    result = await db.execute(
        update(Node)
        .where(
            Node.id == node.id,
            Node.status == NodeStatus.ONLINE,
            Node.accepting_workloads.is_(True),
            Node.reserved_cpu_cores + req.cpu_cores <= Node.allocated_cpu_cores,
            Node.reserved_ram_mb + req.ram_mb <= Node.allocated_ram_mb,
            Node.reserved_disk_mb + req.disk_mb <= Node.allocated_disk_mb,
            Node.reserved_vram_mb + req.vram_mb <= Node.allocated_vram_mb,
        )
        .values(
            reserved_cpu_cores=Node.reserved_cpu_cores + req.cpu_cores,
            reserved_ram_mb=Node.reserved_ram_mb + req.ram_mb,
            reserved_disk_mb=Node.reserved_disk_mb + req.disk_mb,
            reserved_vram_mb=Node.reserved_vram_mb + req.vram_mb,
        )
        .execution_options(synchronize_session=False)
    )
    if _rowcount(result) != 1:
        return False
    db.add(
        ResourceReservation(
            deployment_id=deployment_id,
            node_id=node.id,
            cpu_cores=req.cpu_cores,
            ram_mb=req.ram_mb,
            disk_mb=req.disk_mb,
            vram_mb=req.vram_mb,
        )
    )
    return True


async def schedule(db: AsyncSession, deployment_id, req: ResourceRequest) -> Node:
    ev = await evaluate_nodes(db, req)
    for node in ev.eligible:
        if await try_reserve(db, node, deployment_id, req):
            return node
        ev.reasons[REASON_CAPACITY] += 1  # lost a race for this node's capacity
    raise NoEligibleNode(ev)


async def release_reservation(db: AsyncSession, deployment_id) -> bool:
    """Release a deployment's reservation exactly once. Safe to call repeatedly. Does not commit."""
    reservation = (
        await db.execute(select(ResourceReservation).where(ResourceReservation.deployment_id == deployment_id))
    ).scalar_one_or_none()
    if reservation is None:
        return False
    claimed = await db.execute(
        update(ResourceReservation)
        .where(ResourceReservation.id == reservation.id, ResourceReservation.status == "ACTIVE")
        .values(status="RELEASED", released_at=datetime.utcnow())
        .execution_options(synchronize_session=False)
    )
    if _rowcount(claimed) != 1:
        return False
    await db.execute(
        update(Node)
        .where(Node.id == reservation.node_id)
        .values(
            reserved_cpu_cores=Node.reserved_cpu_cores - reservation.cpu_cores,
            reserved_ram_mb=Node.reserved_ram_mb - reservation.ram_mb,
            reserved_disk_mb=Node.reserved_disk_mb - reservation.disk_mb,
            reserved_vram_mb=Node.reserved_vram_mb - reservation.vram_mb,
        )
        .execution_options(synchronize_session=False)
    )
    return True


# --- Legacy helpers used by the pre-Phase-2 /inference workload path -------------------------------------


async def find_capable_nodes(db, requirements) -> list[Node]:
    requirements = requirements or {}
    query = (
        select(Node)
        .options(joinedload(Node.hardware))
        .where(Node.status.in_((NodeStatus.ONLINE, NodeStatus.AVAILABLE)))
    )
    region = requirements.get("region")
    if region:
        query = query.where(Node.region == region)
    hardware_requirements = requirements.get("requirements", requirements)
    min_vram_gb = hardware_requirements.get("min_vram_gb")
    if hardware_requirements.get("gpu_required") or min_vram_gb is not None:
        query = query.join(NodeHardware, Node.hardware)
        if hardware_requirements.get("gpu_required"):
            query = query.where(NodeHardware.gpu_count > 0)
        if min_vram_gb is not None:
            query = query.where(NodeHardware.gpu_vram_gb >= min_vram_gb)
    result = await db.execute(query)
    return list(result.scalars().unique().all())


def rank_nodes(nodes: list[Node]) -> list[Node]:
    return sorted(
        nodes, key=lambda node: node.reputation_score if node.reputation_score is not None else 0, reverse=True
    )


def select_node(nodes: list[Node]) -> Node | None:
    return nodes[0] if nodes else None
