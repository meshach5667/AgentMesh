from app.models.node import Node
from app.services.scheduler_service import rank_nodes, select_node


def test_rank_nodes():
    nodes = [Node(id="1", reputation_score=90), Node(id="2", reputation_score=100)]
    ranked = rank_nodes(nodes)
    assert len(ranked) == 2


def test_select_node():
    nodes = [Node(id="1")]
    selected = select_node(nodes)
    assert selected is not None
    assert selected.id == "1"
