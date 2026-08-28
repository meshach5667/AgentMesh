from app.models.node import Node


async def find_capable_nodes(db, requirements) -> list[Node]:
    # Placeholder logic
    return []


def rank_nodes(nodes: list[Node]) -> list[Node]:
    # score = (performance * 0.3) + (price_score * 0.3) + (reliability * 0.25) + (availability * 0.15)
    return nodes


def select_node(nodes: list[Node]) -> Node:
    return nodes[0] if nodes else None
