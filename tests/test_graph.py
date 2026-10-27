import networkx as nx
import pytest

from examdiag.graph import (
    ancestor_closure,
    ancestors,
    build,
    descendants,
    detect_cycle,
    distance,
    shortest_path,
    subgraph,
    topo_order,
)
from examdiag.schema import Concept, ConceptGraph


def chain_graph():
    """stack -> recursion -> binary -> traverse -> bst -> rotate 六点链。"""
    ids = [
        "ds.stack.stack", "ds.recursion", "ds.tree.binary",
        "ds.tree.traverse", "ds.bst.bst", "ds.bst.rotate",
    ]
    concepts = [
        Concept(id=cid, name=cid, subject="408", difficulty=3,
                prereqs=[ids[i - 1]] if i else [])
        for i, cid in enumerate(ids)
    ]
    return build(ConceptGraph.from_list(concepts))


def test_build_edges_point_prereq_to_concept():
    g = chain_graph()
    assert g.has_edge("ds.tree.binary", "ds.tree.traverse")
    assert not g.has_edge("ds.tree.traverse", "ds.tree.binary")
    assert g.nodes["ds.bst.rotate"]["name"] == "ds.bst.rotate"


def test_ancestors_and_descendants():
    g = chain_graph()
    assert ancestors(g, "ds.tree.traverse") == {"ds.stack.stack", "ds.recursion", "ds.tree.binary"}
    assert descendants(g, "ds.tree.binary") == {"ds.tree.traverse", "ds.bst.bst", "ds.bst.rotate"}


def test_topo_order_starts_from_root_and_respects_order():
    g = chain_graph()
    order = topo_order(g)
    assert order[0] == "ds.stack.stack"
    assert (
        order.index("ds.tree.binary")
        < order.index("ds.tree.traverse")
        < order.index("ds.bst.rotate")
    )


def test_ancestor_closure_includes_self_and_all_prereqs():
    g = chain_graph()
    closure = ancestor_closure(g, ["ds.bst.rotate", "ds.tree.traverse"])
    assert closure == set(g.nodes)  # 六点全链：两个目标 + 它们的全部前置


def test_ancestor_closure_rejects_unknown_id():
    g = chain_graph()
    with pytest.raises(KeyError):
        ancestor_closure(g, ["ds.ghost.node"])


def test_distance_and_shortest_path():
    g = chain_graph()
    assert distance(g, "ds.stack.stack", "ds.bst.rotate") == 5
    assert shortest_path(g, "ds.stack.stack", "ds.bst.rotate") == list(g.nodes)
    with pytest.raises(ValueError):
        distance(g, "ds.bst.rotate", "ds.stack.stack")  # 反向不可达


def test_detect_cycle_none_and_path():
    g = chain_graph()
    assert detect_cycle(g) is None
    g.add_edge("ds.bst.rotate", "ds.stack.stack")  # 造环
    cycle = detect_cycle(g)
    assert cycle is not None
    assert cycle[0] == cycle[-1]  # 首尾同点


def test_subgraph_keeps_only_induced_edges():
    g = chain_graph()
    sub = subgraph(g, ["ds.stack.stack", "ds.recursion", "ds.bst.rotate"])
    assert set(sub.nodes) == {"ds.stack.stack", "ds.recursion", "ds.bst.rotate"}
    assert set(sub.edges) == {("ds.stack.stack", "ds.recursion")}  # rotate 的入边被截断
    assert isinstance(sub, nx.DiGraph)
