"""根因诊断主算法（SPEC 5.3）。

流程：
1. attempts 按时间排序，每次作答归属到题目挂载的每个概念 → 每概念一条 0/1 序列
2. 概念级 BKT 拟合 → mastery[c] = 最后一次作答后的过滤后验
3. 错题概念集 C_w 及其祖先闭包为候选集；按 SPEC 公式计算
   score(c) = (1-mastery[c]) * Π_{a∈anc(c)} (1-mastery[a])^(1/d(a,c))
   （无数据的前置不进乘积；指数 1/d 让远前置权重衰减）
4. 症状过滤：候选若有掌握度 < MASTERY_THRESHOLD 的有数据前置，则其失败
   可被上游解释，标记为症状而非根因——即 SPEC 第 4 步"祖先闭包内取最上游
   低掌握节点"的实现形式
5. 幸存者按 mastery 升序 + 拓扑序取前 top_n 个为根因；每个根因附：
   涉及错题数（自身或其下游的错题）、到最近错题概念的图距离、
   补习路径（根因 -> 最近错题概念的最短路径）、它解释的下游症状

边界：概念 attempt 数 < MIN_ATTEMPTS(3) 时不参与拟合与根因候选、不进 score
乘积，标记为 insufficient_data。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from .bkt import BKTParams, fit, forward_posterior
from .graph import (
    ancestor_closure,
    ancestors,
    build,
    descendants,
    distance,
    shortest_path,
    topo_order,
)
from .schema import Attempt, ConceptGraph, Question

MIN_ATTEMPTS = 3
MASTERY_THRESHOLD = 0.5  # 低于它视为"未掌握"，用于症状过滤
DEGENERATE_P = 0.5  # p_S/p_G 超过它说明 EM 在小样本上退化了
DEFAULT_INIT = BKTParams(p_L0=0.4, p_T=0.15, p_S=0.15, p_G=0.15)


@dataclass
class RootCause:
    concept_id: str
    name: str
    mastery: float
    score: float
    wrong_count: int
    min_distance: int
    remedy_path: list[str] = field(default_factory=list)
    explains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "name": self.name,
            "mastery": round(self.mastery, 4),
            "score": round(self.score, 6),
            "wrong_count": self.wrong_count,
            "min_distance": self.min_distance,
            "remedy_path": self.remedy_path,
            "explains": self.explains,
        }


@dataclass
class Diagnosis:
    user_id: str | None
    root_causes: list[RootCause]
    insufficient_data: list[str]
    mastery: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "root_causes": [r.to_dict() for r in self.root_causes],
            "insufficient_data": self.insufficient_data,
            "mastery": {k: round(v, 4) for k, v in sorted(self.mastery.items())},
        }


def collect_sequences(
    attempts: Sequence[Attempt], questions: Sequence[Question], user_id: str | None = None
) -> dict[str, list[int]]:
    """按概念归并作答序列：每题归属到它挂载的每个概念，序列按 ts 升序。"""
    qmap = {q.id: q for q in questions}
    rows = [a for a in attempts if user_id is None or a.user_id == user_id]
    if user_id is not None and not rows:
        raise KeyError(f"no attempts for user {user_id!r}")
    rows.sort(key=lambda a: a.ts)
    seqs: dict[str, list[int]] = defaultdict(list)
    for a in rows:
        q = qmap.get(a.question_id)
        if q is None:
            raise KeyError(f"attempt references unknown question {a.question_id!r}")
        for cid in q.concepts:
            seqs[cid].append(int(a.correct))
    return dict(seqs)


def _mastery_of(obs: np.ndarray) -> float:
    """单概念掌握度：EM 拟合后取末次作答的过滤后验。

    全对/全错等极短序列会让 EM 退化（如全错序列把 p_S 顶到上界 0.99，
    拟合成"已掌握但总失误"，与"未掌握"似然相同而后验相反）。检测到
    p_S/p_G 越过 0.5 即视为退化，退回默认参数做前向后验，保证全对→高、
    全错→低的直觉排序。
    """
    params = fit([obs])
    if params.p_S > DEGENERATE_P or params.p_G > DEGENERATE_P:
        params = DEFAULT_INIT
    return float(forward_posterior(obs, params)[-1])


def estimate_mastery(seqs: dict[str, list[int]]) -> tuple[dict[str, float], list[str]]:
    """逐概念拟合给出末次作答后的掌握后验；样本不足的进 insufficient。"""
    mastery: dict[str, float] = {}
    insufficient: list[str] = []
    for cid, seq in sorted(seqs.items()):
        if len(seq) < MIN_ATTEMPTS:
            insufficient.append(cid)
            continue
        mastery[cid] = _mastery_of(np.asarray(seq, dtype=bool))
    return mastery, sorted(insufficient)


def score(g: nx.DiGraph, cid: str, mastery: dict[str, float]) -> float:
    """SPEC 5.3 公式：(1-mastery[c]) * Π (1-mastery[a])^(1/d(a,c))，无数据前置跳过。"""
    prod = 1.0
    for a in ancestors(g, cid):
        if a not in mastery:
            continue
        d = distance(g, a, cid)
        prod *= (1.0 - mastery[a]) ** (1.0 / d)
    return (1.0 - mastery[cid]) * prod


def diagnose(
    attempts: Sequence[Attempt],
    questions: Sequence[Question],
    concepts: ConceptGraph,
    user_id: str | None = None,
    top_n: int = 3,
) -> Diagnosis:
    g = build(concepts)
    qmap = {q.id: q for q in questions}
    seqs = collect_sequences(attempts, questions, user_id)
    mastery, insufficient = estimate_mastery(seqs)

    wrong_by_concept: Counter[str] = Counter()
    for a in attempts:
        if user_id is not None and a.user_id != user_id:
            continue
        if a.correct:
            continue
        for cid in qmap[a.question_id].concepts:
            wrong_by_concept[cid] += 1
    wrong_concepts = set(wrong_by_concept)
    if not wrong_concepts:
        return Diagnosis(
            user_id=user_id, root_causes=[], insufficient_data=insufficient, mastery=mastery
        )

    closure = ancestor_closure(g, wrong_concepts)
    candidates = {c for c in closure if c in mastery}
    topo_idx = {cid: i for i, cid in enumerate(topo_order(g))}

    # 症状过滤：有未掌握前置的概念是症状，不是根因；根因自身也必须未掌握
    survivors = [
        c
        for c in candidates
        if mastery[c] < MASTERY_THRESHOLD
        and not any(
            a in mastery and mastery[a] < MASTERY_THRESHOLD for a in ancestors(g, c)
        )
    ]
    survivors.sort(key=lambda c: (mastery[c], topo_idx[c]))

    root_causes: list[RootCause] = []
    for r in survivors[:top_n]:
        # 根因必然可达至少一个错题概念（r ∈ C_w 或其祖先）；跨分支的不可达概念跳过
        reachable = []
        for w in wrong_concepts:
            try:
                reachable.append((distance(g, r, w), topo_idx[w], w))
            except ValueError:
                continue
        min_dist = min(d for d, _, _ in reachable)
        # 补习终点取可达的最深错题概念：从根因一路补到最终要攻克的目标
        _, _, goal = max(reachable)
        desc = descendants(g, r)
        root_causes.append(
            RootCause(
                concept_id=r,
                name=concepts.concepts[r].name,
                mastery=mastery[r],
                score=score(g, r, mastery),
                wrong_count=sum(
                    cnt for cid, cnt in wrong_by_concept.items() if cid == r or cid in desc
                ),
                min_distance=min_dist,
                remedy_path=shortest_path(g, r, goal),
                explains=sorted(
                    (w for w in wrong_concepts if w in desc), key=topo_idx.__getitem__
                ),
            )
        )
    return Diagnosis(
        user_id=user_id,
        root_causes=root_causes,
        insufficient_data=insufficient,
        mastery=mastery,
    )
