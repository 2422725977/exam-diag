"""生成 data/demo_attempts_multi.jsonl：3 个用户、三条不同方向的薄弱链。

  demo-a（408）  树遍历 → AVL：traverse 先对后连错，rotate/delete 全错，前置掌握
  demo-b（408）  进程调度 → 死锁：sched 全错、deadlock 几乎全错，process/sync 掌握
                 （图谱里 deadlock 的前置是 sync 而非 sched，诊断会给出两个根因，调度更弱排第一）
  demo-c（math1）期望 → 方差：expectation 弱、variance 全错，discrete/cont 掌握
                 （图谱没有"条件期望"节点，链取真实前置边 variance ← expectation；
                  cond 保持基本掌握，避免衍生多余根因）

每人 150-200 条（植入 20-36 条 + 填充 ~140 条、80% 正确率）。seed 固定可复现。
运行：python scripts/make_demo_attempts_multi.py
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261101
FILLER_CORRECT_P = 0.80

PLANTED: dict[str, dict[str, list[int]]] = {
    "demo-a": {
        "ds.stack.stack": [1, 1, 1, 1],
        "ds.recursion": [1, 1, 1, 1],
        "ds.tree.binary": [1, 1, 1, 1, 0],
        "ds.bst.bst": [1, 0, 1, 1, 0],
        "ds.tree.traverse": [1, 1, 1, 0, 0, 0, 0, 0],
        "ds.bst.rotate": [0, 0, 0, 0, 0, 0],
        "ds.bst.delete": [0, 0, 0, 0],
    },
    "demo-b": {
        "os.process.process": [1, 1, 1, 1, 1],
        "os.process.sync": [1, 1, 1, 1],
        "os.process.sched": [0, 0, 0, 0, 0, 0],
        "os.process.deadlock": [0, 1, 1, 0, 0, 0],
    },
    "demo-c": {
        "math.prob.discrete": [1, 1, 1, 1],
        "math.prob.cont": [1, 1, 1, 1, 1],
        "math.prob.cond": [1, 1, 1, 1, 0],
        "math.prob.expectation": [0, 1, 0, 0, 1, 0],
        "math.prob.variance": [0, 0, 0, 0, 0, 0],
    },
}
SUBJECT_FILES = {"demo-a": "408", "demo-b": "408", "demo-c": "math1"}
TARGET = {"demo-a": 166, "demo-b": 161, "demo-c": 166}


def load_questions() -> dict[str, list]:
    pools: dict[str, list] = defaultdict(list)
    for subj in set(SUBJECT_FILES.values()):
        with open(ROOT / f"data/questions/{subj}.jsonl", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    q = json.loads(line)
                    for cid in q["concepts"]:
                        pools[cid].append(q)
    return pools


def main() -> None:
    rng = random.Random(SEED)
    pools = load_questions()
    rows = []

    for user, planted in PLANTED.items():
        planted_ids = set(planted)
        # 填充题池：整题不触碰任何植入概念，避免稀释模式
        clean: dict[str, list] = {}
        for cid, qs in pools.items():
            if cid in planted_ids:
                continue
            ok = [q for q in qs if not (set(q["concepts"]) & planted_ids)]
            if ok:
                clean[cid] = ok
        n_planted = sum(len(v) for v in planted.values())
        n_filler = TARGET[user] - n_planted

        streams = {cid: list(seq) for cid, seq in planted.items()}
        filler_concepts = sorted(clean)
        per_user_filler: dict[str, list[int]] = defaultdict(list)
        for _ in range(n_filler):
            cid = rng.choice(filler_concepts)
            per_user_filler[cid].append(1 if rng.random() < FILLER_CORRECT_P else 0)

        # 多流归并：保持每个概念内部顺序，时间线交错
        merged: list[tuple[str, int]] = []
        while any(streams.values()) or any(per_user_filler.values()):
            avail = [c for c, s in streams.items() if s] + [
                c for c, s in per_user_filler.items() if s
            ]
            cid = rng.choice(avail)
            if streams.get(cid):
                merged.append((cid, streams[cid].pop(0)))
            else:
                merged.append((cid, per_user_filler[cid].pop(0)))
        assert len(merged) == TARGET[user]

        t = datetime(2026, 10, 14, 8, 0, 0)
        for cid, ok in merged:
            # 植入事件的题不得挂其他植入概念，防止综合题把作答泄进别的植入链
            pool = [q for q in pools[cid] if not (set(q["concepts"]) & planted_ids - {cid})]
            q = rng.choice(pool or pools[cid])
            t += timedelta(minutes=rng.randint(8, 45))
            rows.append(
                {"user_id": user, "question_id": q["id"], "correct": bool(ok),
                 "ts": t.isoformat()}
            )

    out = ROOT / "data/demo_attempts_multi.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    per_user: dict[str, int] = defaultdict(int)
    for r in rows:
        per_user[r["user_id"]] += 1
    print(f"written {out} rows={len(rows)}")
    for u in sorted(per_user):
        print(f"  {u}: {per_user[u]} attempts")


if __name__ == "__main__":
    main()
