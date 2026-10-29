"""生成 viz/report.html（原实现已下沉为 examdiag/report.py，本脚本为薄包装）。

运行：python scripts/make_report.py
"""

from __future__ import annotations

from pathlib import Path

from examdiag.diagnose import diagnose
from examdiag.report import write_html
from examdiag.schema import load_attempts, load_concepts, load_questions

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "viz/report.html"


def main() -> None:
    concepts = load_concepts(ROOT / "data/concepts/408.yaml")
    questions = load_questions(ROOT / "data/questions/408.jsonl")
    attempts = load_attempts(ROOT / "data/demo_attempts.jsonl")
    cmd = "examdiag diagnose --attempts data/demo_attempts.jsonl --concepts data/concepts/"
    diag = diagnose(attempts, questions, concepts)
    out = write_html(diag, concepts, attempts, questions, OUT, cmd_line=cmd)
    causes = [r.concept_id for r in diag.root_causes]
    print(f"written {out} ({out.stat().st_size / 1024:.0f} KB), causes={causes}")


if __name__ == "__main__":
    main()
