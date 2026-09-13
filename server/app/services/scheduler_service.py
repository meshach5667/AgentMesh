from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.node import Node, NodeHardware, NodeStatus


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
        nodes,
        key=lambda node: node.reputation_score if node.reputation_score is not None else 0,
        reverse=True,
    )


def select_node(nodes: list[Node]) -> Node:
    return nodes[0] if nodes else None
