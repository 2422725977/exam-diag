"""Wave 0 数据验收脚本。

用法：
  python scripts/validate_data.py concepts data/concepts/408.yaml --subject 408 [--expect 60]
  python scripts/validate_data.py questions data/questions/408.jsonl --subject 408 \
      --concepts data/concepts/408.yaml [--expect 150]
  python scripts/validate_data.py all          # 四科概念 + 四科题目 + 跨文件 id 唯一

退出码非 0 表示有验收项不通过；stdout 逐项打印 PASS/FAIL。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from examdiag.schema import load_concepts  # noqa: E402

SUBJECTS = ("408", "math1", "english", "politics")
ROOT = Path(__file__).resolve().parent.parent

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def depth_of(graph) -> int:
    """最长前置链长度（层数）。"""
    memo: dict[str, int] = {}

    def d(cid: str) -> int:
        if cid in memo:
            return memo[cid]
        prereqs = graph.concepts[cid].prereqs
        memo[cid] = 1 + max((d(p) for p in prereqs), default=0)
        return memo[cid]

    return max(d(cid) for cid in graph.concepts)


def validate_concepts(path: Path, subject: str, expect: int = 60, strict: bool = True) -> None:
    print(f"\n== concepts: {path} ==")
    try:
        g = load_concepts(path)
    except Exception as e:  # noqa: BLE001
        check(f"{path}: schema 加载", False, repr(e))
        return
    check(f"{path}: schema 加载（含 prereq 引用与无环）", True)
    check(f"{path}: 节点数 == {expect}", len(g.concepts) == expect, f"actual={len(g.concepts)}")
    bad_subject = [cid for cid, c in g.concepts.items() if c.subject != subject]
    check(f"{path}: 所有节点 subject == {subject}", not bad_subject, f"bad={bad_subject[:3]}")
    roots = g.roots()
    dependents: dict[str, int] = dict.fromkeys(g.concepts, 0)
    for c in g.concepts.values():
        for p in c.prereqs:
            dependents[p] += 1
    isolated = [cid for cid in g.concepts if not g.concepts[cid].prereqs and dependents[cid] == 0]
    if strict:
        check(f"{path}: 无孤立节点（根节点均有后继）", not isolated, f"isolated={isolated[:5]}")
    else:
        check(f"{path}: 根节点数 <= 40", len(roots) <= 40, f"roots={len(roots)}")
    d = depth_of(g)
    print(f"       stats: nodes={len(g.concepts)} roots={len(roots)} "
          f"sinks={sum(1 for v in dependents.values() if v == 0)} depth={d} edges="
          f"{sum(len(c.prereqs) for c in g.concepts.values())}")


def validate_questions(
    path: Path, subject: str, concepts_path: Path, expect: int = 150, expect_min: int | None = None
) -> None:
    print(f"\n== questions: {path} ==")
    g = load_concepts(concepts_path)
    ids: list[str] = []
    rows = []
    ok_json = True
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
                ids.append(rows[-1].get("id", "<missing>"))
            except json.JSONDecodeError as e:
                ok_json = False
                print(f"       line {i}: JSON error {e}")
    check(f"{path}: 每行合法 JSON", ok_json)
    if expect_min is None:
        check(f"{path}: 行数 == {expect}", len(rows) == expect, f"actual={len(rows)}")
    else:
        check(f"{path}: 行数 >= {expect_min}（目标 {expect}）", len(rows) >= expect_min,
              f"actual={len(rows)}")
    dup_ids = sorted({x for x in set(ids) if ids.count(x) > 1})
    check(f"{path}: id 无重复", not dup_ids, f"dups={dup_ids[:5]}")
    bad_subject = [r.get("id") for r in rows if r.get("subject") != subject]
    check(f"{path}: 所有题 subject == {subject}", not bad_subject, f"bad={bad_subject[:3]}")
    unknown = [
        (r.get("id"), cid)
        for r in rows
        for cid in r.get("concepts", [])
        if cid not in g.concepts
    ]
    check(f"{path}: concepts 全部可解析", not unknown, f"unknown={unknown[:5]}")
    no_concept = [r.get("id") for r in rows if not r.get("concepts")]
    check(f"{path}: 每题 >=1 个 concept", not no_concept, f"empty={no_concept[:5]}")
    no_source = [r.get("id") for r in rows if not str(r.get("source", "")).strip()]
    check(f"{path}: source 非空", not no_source, f"empty={no_source[:5]}")


def validate_all() -> None:
    for subject in SUBJECTS:
        validate_concepts(ROOT / f"data/concepts/{subject}.yaml", subject,
                          strict=(subject != "english"))
    seen: dict[str, str] = {}
    dups: list[str] = []
    for subject in SUBJECTS:
        path = ROOT / f"data/concepts/{subject}.yaml"
        if not path.exists():
            continue
        g = load_concepts(path)
        for cid in g.concepts:
            if cid in seen:
                dups.append(f"{cid} in {seen[cid]} & {subject}")
            else:
                seen[cid] = subject
    check("跨文件 concept id 唯一", not dups, f"dups={dups[:5]}")
    for subject in SUBJECTS:
        qpath = ROOT / f"data/questions/{subject}.jsonl"
        cpath = ROOT / f"data/concepts/{subject}.yaml"
        if qpath.exists() and cpath.exists():
            # SPEC：超时时 408/math1 必须满 150，english/politics 可降级到 60
            if subject in ("408", "math1"):
                validate_questions(qpath, subject, cpath, expect=150)
            else:
                validate_questions(qpath, subject, cpath, expect=150, expect_min=60)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("concepts")
    pc.add_argument("path", type=Path)
    pc.add_argument("--subject", required=True)
    pc.add_argument("--expect", type=int, default=60)
    pq = sub.add_parser("questions")
    pq.add_argument("path", type=Path)
    pq.add_argument("--subject", required=True)
    pq.add_argument("--concepts", required=True, type=Path)
    pq.add_argument("--expect", type=int, default=150)
    sub.add_parser("all")
    args = parser.parse_args()

    if args.cmd == "concepts":
        validate_concepts(args.path, args.subject, args.expect, strict=(args.subject != "english"))
    elif args.cmd == "questions":
        validate_questions(args.path, args.subject, args.concepts, args.expect)
    else:
        validate_all()

    print()
    if failures:
        print(f"RESULT: {len(failures)} check(s) FAILED: {failures}")
        return 1
    print("RESULT: all checks PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
