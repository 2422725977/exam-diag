# ruff: noqa: E501
"""把 ASSISTments skill-builder 原始 CSV 转成 examdiag 数据格式（Wave 3 任务 3.2）。

输入：data/real/raw/skill_builder_data.csv（官方 corrected 版，346,860 行）
输出：
  data/real/assistments.jsonl          Attempt 格式 {user_id, question_id, correct, ts}
  data/real/skills.jsonl               {question_id, skill} 唯一映射对
  data/real/concepts_assistments.yaml  101 个技能 → 概念节点（与 Concept 字段同构）
  data/real/CONVERSION_REPORT.md       真实转换统计（进/弃行数与原因）

规则（全部如实统计，不许静默丢弃）：
  - correct 必须 ∈ {0,1}，其余丢弃；
  - user_id / problem_id / skill_name 任一为空即丢弃；
  - ts 由 order_id 合成（2000-01-01 起、秒级单调），BKT 只依赖序列顺序，
    原始数据无逐条时间戳，此为文档化处理而非编造；
  - skills 与 questions 一对一校验：同一 problem_id 若挂多个 skill，映射表按
    (question_id, skill) 唯一对输出并在报告计数。

运行：python scripts/convert_assistments.py
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/real/raw/skill_builder_data.csv"
OUT_DIR = ROOT / "data/real"
TS_BASE = datetime(2000, 1, 1)


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "skill"


def main() -> None:
    stats: Counter[str] = Counter()
    rows_out: list[dict] = []
    q2skills: dict[str, set[str]] = defaultdict(set)
    skill_rows: Counter[str] = Counter()

    with open(RAW, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["rows_in"] += 1
            uid = row["user_id"].strip()
            pid = row["problem_id"].strip()
            correct = row["correct"].strip()
            skill = row["skill_name"].strip()
            order = row["order_id"].strip()
            if not uid or not pid:
                stats["drop_missing_user_or_problem"] += 1
                continue
            if not skill:
                stats["drop_empty_skill"] += 1
                continue
            if correct not in ("0", "1"):
                stats["drop_correct_not_binary"] += 1
                continue
            qid = f"p{pid}"
            ts = (TS_BASE + timedelta(seconds=int(order))).isoformat()
            rows_out.append(
                {"user_id": uid, "question_id": qid, "correct": correct == "1", "ts": ts}
            )
            q2skills[qid].add(skill)
            skill_rows[skill] += 1
            stats["attempts_out"] += 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "assistments.jsonl", "w", encoding="utf-8") as f:
        for r in rows_out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "skills.jsonl", "w", encoding="utf-8") as f:
        for qid in sorted(q2skills):
            for sk in sorted(q2skills[qid]):
                f.write(json.dumps({"question_id": qid, "skill": sk}, ensure_ascii=False) + "\n")

    # 概念文件（与 Concept 字段同构；subject 为数据集名，
    # 不走 examdiag.schema 四科枚举校验——真实数据集不属于四科）
    lines = ["# ASSISTments skill-builder 概念（= 数据集自带 skill 标注）",
             "# difficulty 真实值未知，统一中性 3.0；prereqs 空（BKT 逐技能独立，无前置图）",
             "subject: \"assistments\"", "concepts:"]
    for sk in sorted(skill_rows):
        lines.append(
            f"  - {{id: asst.{slugify(sk)}, name: \"{sk}\", subject: \"assistments\", "
            f"difficulty: 3.0, prereqs: []}}"
        )
    (OUT_DIR / "concepts_assistments.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    users = {r["user_id"] for r in rows_out}
    multi = sum(1 for q, s in q2skills.items() if len(s) > 1)
    report = [
        "# ASSISTments 转换报告（真实统计）", "",
        f"- 输入行数：{stats['rows_in']:,}",
        f"- 输出 attempts：{stats['attempts_out']:,}（用户 {len(users):,}，question "
        f"{len(q2skills):,}，skill {len(skill_rows)}）",
        f"- 丢弃行：缺 user/problem {stats['drop_missing_user_or_problem']:,}；"
        f"空 skill {stats['drop_empty_skill']:,}；correct 非 0/1 "
        f"{stats['drop_correct_not_binary']:,}",
        f"- 一题多技能：{multi} 个 question（映射表按 (question_id, skill) 唯一对展开）",
        "- ts 说明：由 order_id 合成单调时间戳（原始数据无逐条时间）",
    ]
    (OUT_DIR / "CONVERSION_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
