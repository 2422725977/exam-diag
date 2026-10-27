"""DAG 操作层（networkx）：拓扑序、祖先闭包、最短路径、环检测。

图方向统一为 前置概念 -> 后继概念（prereq -> concept），
因此 nx.ancestors(g, c) 即 c 的全部前置，nx.descendants(g, c) 即依赖 c 的概念。
schema.ConceptGraph 在加载时已做环检测；本模块对已构建的 DiGraph 再暴露
独立环检测，供 Wave 1 的诊断流程与测试复用。
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

import networkx as nx

from .schema import ConceptGraph


def build(concepts: ConceptGraph) -> nx.DiGraph:
    """从 ConceptGraph 构建 networkx 有向图（前置 -> 后继），节点带 name/difficulty 属性。"""
    g = nx.DiGraph()
    for cid, c in concepts.concepts.items():
        g.add_node(cid, name=c.name, difficulty=c.difficulty, subject=c.subject)
    for cid, c in concepts.concepts.items():
        for p in c.prereqs:
            g.add_edge(p, cid)
    return g


def detect_cycle(g: nx.DiGraph) -> list[str] | None:
    """返回一条环路路径（首尾同点）；无环返回 None。"""
    try:
        cycle = nx.find_cycle(g, orientation="original")
    except nx.NetworkXNoCycle:
        return None
    # find_cycle 返回边列表 [(u, v, dir), ...]，串成节点路径
    path = [cycle[0][0]]
    for _u, v, _d in cycle:
        path.append(v)
    return path


def topo_order(g: nx.DiGraph) -> list[str]:
    """拓扑序（networkx lexicographical 变体保证同层确定性）。"""
    return list(nx.lexicographical_topological_sort(g))


def ancestors(g: nx.DiGraph, cid: str) -> set[str]:
    return nx.ancestors(g, cid)


def descendants(g: nx.DiGraph, cid: str) -> set[str]:
    return nx.descendants(g, cid)


def ancestor_closure(g: nx.DiGraph, cids: Iterable[str]) -> set[str]:
    """cids 及其全部传递前置。"""
    ids = set(cids)
    missing = ids - set(g.nodes)
    if missing:
        raise KeyError(f"unknown concept id(s): {sorted(missing)}")
    closure: set[str] = set(ids)
    for cid in ids:
        closure |= nx.ancestors(g, cid)
    return closure


def subgraph(g: nx.DiGraph, nodes: Iterable[str]) -> nx.DiGraph:
    return g.subgraph(set(nodes)).copy()


def distance(g: nx.DiGraph, src: str, dst: str) -> int:
    """沿前置方向 src -> dst 的最短距离；不可达抛 ValueError。"""
    try:
        return nx.shortest_path_length(g, src, dst)
    except nx.NetworkXNoPath as e:
        raise ValueError(f"no path from {src} to {dst}") from e


def shortest_path(g: nx.DiGraph, src: str, dst: str) -> list[str]:
    """src -> dst 最短路径上的概念序列（含两端）。"""
    try:
        return nx.shortest_path(g, src, dst)
    except nx.NetworkXNoPath as e:
        raise ValueError(f"no path from {src} to {dst}") from e


def iter_reachable_targets(
    g: nx.DiGraph, src: str, targets: Iterable[str]
) -> Iterator[tuple[str, int]]:
    """依次产出 (target, distance)：src 可达的 targets，按距离升序、id 升序。"""
    out = []
    for t in targets:
        try:
            out.append((t, nx.shortest_path_length(g, src, t)))
        except nx.NetworkXNoPath:
            continue
    return iter(sorted(out, key=lambda x: (x[1], x[0])))
