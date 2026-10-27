"""生成 data/demo_attempts.jsonl：500 条单用户作答，植入可诊断的根因模式。

模式（SPEC Wave 1 任务 1.5）：
  - 结尾连续 10 次作答：ds.bst.rotate 全错 ×6 + ds.bst.delete 全错 ×4（"BST 旋转变形题连续错"）
  - ds.tree.traverse 先对 3 后连错 5（其前置"二叉树遍历"也错，且是下滑趋势）
  - 前置概念掌握良好：ds.stack.stack / ds.recursion 全对，ds.tree.binary 4/5，
    ds.bst.bst 3/5（基础 BST 尚可，旋转不行）
  - 其余 408 概念填充 ~464 条、80% 正确率（真实感背景）

时间线：按"多流归并"交错（保持每个概念内部的作答顺序），末尾追加连续错窗口。
seed 固定，输出可复现。运行：python scripts/make_demo_attempts.py
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261028
N_TOTAL = 500

# 植入模式：概念 -> 作答序列（1=对 0=错），顺序即该概念的时间顺序
PLANTED: dict[str, list[int]] = {
    "ds.stack.stack": [1, 1, 1, 1],
    "ds.recursion": [1, 1, 1, 1],
    "ds.tree.binary": [1, 1, 1, 1, 0],
    "ds.bst.bst": [1, 0, 1, 1, 0],
    "ds.tree.traverse": [1, 1, 1, 0, 0, 0, 0, 0],
}
ENDING_STREAK: dict[str, list[int]] = {
    "ds.bst.rotate": [0, 0, 0, 0, 0, 0],
    "ds.bst.delete": [0, 0, 0, 0],
}
FILLER_CORRECT_P = 0.80


def main() -> None:
    rng = random.Random(SEED)
    questions: dict[str, list] = defaultdict(list)
    all_q = []
    with open(ROOT / "data/questions/408.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                all_q.append(q)
                for cid in q["concepts"]:
                    questions[cid].append(q)

    planted_ids = set(PLANTED) | set(ENDING_STREAK)
    # 填充题池：主概念未植入、且整题不触碰任何植入概念（避免稀释植入模式）
    clean_questions: dict[str, list] = {}
    for cid, qs in questions.items():
        if cid in planted_ids:
            continue
        pool = [q for q in qs if not (set(q["concepts"]) & planted_ids)]
        if pool:
            clean_questions[cid] = pool
    filler_concepts = sorted(clean_questions)
    n_planted = sum(len(v) for v in PLANTED.values()) + sum(
        len(v) for v in ENDING_STREAK.values()
    )
    n_filler = N_TOTAL - n_planted
    assert n_filler > 0, "植入序列超出总量"

    # 每个填充概念的作答流（概念内保持顺序）
    per = n_filler // len(filler_concepts)
    streams: list[list[tuple[str, int]]] = [
        [(cid, 1 if rng.random() < FILLER_CORRECT_P else 0) for _ in range(per)]
        for cid in filler_concepts
    ]
    # 余数随机分配
    for _ in range(n_filler % len(filler_concepts)):
        cid = rng.choice(filler_concepts)
        for stream in streams:
            if stream and stream[0][0] == cid:
                stream.append((cid, 1 if rng.random() < FILLER_CORRECT_P else 0))
                break

    merged: list[tuple[str, int]] = []
    pending = {cid: list(seq) for cid, seq in PLANTED.items()}
    filler_by_cid: dict[str, list[int]] = defaultdict(list)
    for s in streams:
        for cid, ok in s:
            filler_by_cid[cid].append(ok)

    # 交错：每一拍以概率挑一个"还有货"的流
    while any(pending.values()) or any(filler_by_cid.values()):
        available = [cid for cid, seq in pending.items() if seq] + [
            cid for cid, seq in filler_by_cid.items() if seq
        ]
        cid = rng.choice(available)
        if cid in pending and pending[cid]:
            merged.append((cid, pending[cid].pop(0)))
        else:
            merged.append((cid, filler_by_cid[cid].pop(0)))

    # 末尾追加"连续错"窗口（rotate + delete，时间连续）
    streak = [(cid, ok) for cid, seq in ENDING_STREAK.items() for ok in seq]
    merged.extend(streak)
    assert len(merged) == N_TOTAL, f"expected {N_TOTAL}, got {len(merged)}"

    t = datetime(2026, 10, 12, 9, 0, 0)
    rows = []
    for cid, ok in merged:
        pool = clean_questions.get(cid) or questions[cid]
        q = rng.choice(pool)
        t += timedelta(minutes=rng.randint(8, 50))
        rows.append(
            {"user_id": "demo-user", "question_id": q["id"], "correct": bool(ok),
             "ts": t.isoformat()}
        )

    out = ROOT / "data/demo_attempts.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 自检输出
    per_concept: dict[str, list[int]] = defaultdict(list)
    qmap = {q["id"]: q for q in all_q}
    for r in rows:
        for cid in qmap[r["question_id"]]["concepts"]:
            per_concept[cid].append(int(r["correct"]))
    print(f"written {out} rows={len(rows)} users=1")
    for cid in sorted(planted_ids):
        seq = per_concept[cid]
        print(f"  {cid:22s} attempts={len(seq):2d} acc={sum(seq)}/{len(seq)}")


if __name__ == "__main__":
    main()
