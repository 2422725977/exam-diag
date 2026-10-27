"""Core data models: Concept / Question / Attempt / ConceptGraph.

中文文本字段一律 UTF-8 str。prereqs 引用校验在 ConceptGraph 里做：
未知前置 id 或成环都会抛 ValueError，环路报错里带具体路径。
"""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

Subject = Literal["408", "math1", "english", "politics"]


class Concept(BaseModel):
    """知识点节点；id 用点分层级（如 ds.bst.rotate），prereqs 指向前置概念 id。"""

    id: str = Field(pattern=r"^[a-z][a-z0-9]*(\.[a-z0-9_-]+)+$")
    name: str = Field(min_length=1)
    subject: Subject
    difficulty: float = Field(ge=1.0, le=5.0)
    prereqs: list[str] = Field(default_factory=list)

    @field_validator("subject", mode="before")
    @classmethod
    def _coerce_subject(cls, v: object) -> object:
        # YAML 会把未加引号的 408 解析成 int，这里拉回字符串
        return str(v) if isinstance(v, int) else v


class Question(BaseModel):
    """题目；concepts 里主概念排第一，source 用真题出处或 self-built。"""

    id: str = Field(min_length=1)
    subject: Subject
    stem: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    concepts: list[str] = Field(min_length=1)
    source: str = Field(min_length=1)

    @field_validator("subject", mode="before")
    @classmethod
    def _coerce_subject(cls, v: object) -> object:
        return str(v) if isinstance(v, int) else v


class Attempt(BaseModel):
    """一次作答记录；ts 需要能排序，BKT 按序列顺序消费。"""

    user_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    correct: bool
    ts: datetime


class ConceptGraph(BaseModel):
    """一批概念的集合，加载时校验 prereq 引用与无环性。"""

    concepts: dict[str, Concept]

    @classmethod
    def from_list(cls, items: list[Concept]) -> ConceptGraph:
        return cls(concepts={c.id: c for c in items})

    @model_validator(mode="after")
    def _check_references_and_cycles(self) -> ConceptGraph:
        self.check_prereq_ids()
        self.check_acyclic()
        return self

    def check_prereq_ids(self) -> None:
        unknown = [
            (c.id, p)
            for c in self.concepts.values()
            for p in c.prereqs
            if p not in self.concepts
        ]
        if unknown:
            sample = ", ".join(f"{cid}->{p}" for cid, p in unknown[:5])
            raise ValueError(f"unknown prereq id(s) ({len(unknown)}): {sample}")

    def find_cycle(self) -> list[str] | None:
        """迭代式 DFS 找环，返回环路路径（首尾同点）；无环返回 None。"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = dict.fromkeys(self.concepts, WHITE)
        for start in self.concepts:
            if color[start] != WHITE:
                continue
            color[start] = GRAY
            stack = [(start, iter(self.concepts[start].prereqs))]
            path = [start]
            while stack:
                node, it = stack[-1]
                advanced = False
                for nxt in it:
                    if color[nxt] == GRAY:
                        return path[path.index(nxt):] + [nxt]
                    if color[nxt] == WHITE:
                        color[nxt] = GRAY
                        stack.append((nxt, iter(self.concepts[nxt].prereqs)))
                        path.append(nxt)
                        advanced = True
                        break
                if not advanced:
                    color[node] = BLACK
                    stack.pop()
                    path.pop()
        return None

    def check_acyclic(self) -> None:
        cycle = self.find_cycle()
        if cycle:
            raise ValueError("prereq cycle detected: " + " -> ".join(cycle))

    def roots(self) -> list[str]:
        """无前置的节点 id，保持声明顺序。"""
        return [cid for cid, c in self.concepts.items() if not c.prereqs]

    def topo_order(self) -> list[str]:
        """Kahn 拓扑序（同层按 id 排序保证确定性）；有环时抛 ValueError。"""
        indeg = dict.fromkeys(self.concepts, 0)
        dependents: dict[str, list[str]] = {cid: [] for cid in self.concepts}
        for c in self.concepts.values():
            for p in c.prereqs:
                indeg[c.id] += 1
                dependents[p].append(c.id)
        queue = deque(sorted(cid for cid, d in indeg.items() if d == 0))
        order: list[str] = []
        while queue:
            n = queue.popleft()
            order.append(n)
            for m in sorted(dependents[n]):
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        if len(order) != len(self.concepts):
            raise ValueError("graph has a cycle; topo order undefined")
        return order

    def ancestors(self, cid: str) -> set[str]:
        """cid 的全部传递前置（不含自身）。"""
        seen: set[str] = set()
        stack = list(self.concepts[cid].prereqs)
        while stack:
            p = stack.pop()
            if p in seen:
                continue
            seen.add(p)
            stack.extend(self.concepts[p].prereqs)
        return seen


# ---------- 文件加载 ----------


def load_concepts(path: str | Path) -> ConceptGraph:
    """加载科目概念文件；接受 {concepts: [...]} 或裸列表两种 YAML 形状。"""
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    items = raw["concepts"] if isinstance(raw, dict) else raw
    return ConceptGraph.from_list([Concept(**item) for item in items])


def load_questions(path: str | Path) -> list[Question]:
    out: list[Question] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(Question(**json.loads(line)))
    return out


def load_attempts(path: str | Path) -> list[Attempt]:
    out: list[Attempt] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(Attempt(**json.loads(line)))
    return out
