"""生成 examples/demo.ipynb（Wave 2 任务 2.4），随后用 nbclient 试运行验证。"""

from __future__ import annotations

import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(
        "# exam-diag demo\n\n"
        "输入一批作答记录，输出**根因概念**（最该补的上游知识点）+ 补习路径 + 7 天复习计划。\n\n"
        "直接 `jupyter lab` / `VS Code` 打开本笔记本从头跑到尾即可，无需联网。"
    ),
    nbf.v4.new_code_cell(
        "from examdiag.diagnose import diagnose\n"
        "from examdiag.schema import load_attempts, load_concepts, load_questions\n"
        "from examdiag.srs import plan_week\n\n"
        "concepts = load_concepts('../data/concepts/408.yaml')\n"
        "questions = load_questions('../data/questions/408.jsonl')\n"
        "attempts = load_attempts('../data/demo_attempts.jsonl')\n"
        "print(f'attempts={len(attempts)} questions={len(questions)} '\n"
        "      f'concepts={len(concepts.concepts)}')"
    ),
    nbf.v4.new_markdown_cell(
        "## 1. 根因诊断\n\n"
        "对每个概念拟合 BKT（EM）得到掌握度，错题沿前置图向上游回溯：\n"
        "前置也未掌握的概念是症状，最上游的破损概念才是根因。"
    ),
    nbf.v4.new_code_cell(
        "diag = diagnose(attempts, questions, concepts)\n\n"
        "for i, r in enumerate(diag.root_causes, 1):\n"
        "    print(f'#{i} {r.name} ({r.concept_id})')\n"
        "    print(f'   掌握度 {r.mastery:.2f} | 错题 {r.wrong_count} | 距离 {r.min_distance}')\n"
        "    print('   补习路径:', ' → '.join(concepts.concepts[c].name for c in r.remedy_path))\n"
        "    explained = '、'.join(concepts.concepts[c].name for c in r.explains)\n"
        "    print('   解释症状:', explained or '—')\n"
        "    print()"
    ),
    nbf.v4.new_markdown_cell(
        "## 2. 未来 7 天复习计划\n\n"
        "间隔与掌握度成反比：掌握度越低，出现越频繁。"
    ),
    nbf.v4.new_code_cell(
        "for p in plan_week(diag):\n"
        "    names = [concepts.concepts[c].name for c in p.concepts]\n"
        "    print(f'Day {p.day}:', '、'.join(names) if names else '（休息）')"
    ),
    nbf.v4.new_markdown_cell("## 3. 全部概念掌握度一览（诊断涉及到的）"),
    nbf.v4.new_code_cell(
        "rows = sorted(diag.mastery.items(), key=lambda kv: kv[1])\n"
        "for cid, m in rows[:8]:\n"
        "    bar = '█' * round(m * 30)\n"
        "    print(f'{concepts.concepts[cid].name:12s} {m:5.2f} |{bar:<30}| {cid}')\n"
        "print(f'... 共 {len(rows)} 个有数据概念')"
    ),
    nbf.v4.new_markdown_cell(
        "## 4. 更多\n\n"
        "- `viz/report.html`：浏览器打开，依赖图 + 掌握度着色 + 点击查看涉及错题\n"
        "- `examdiag diagnose --attempts ... --concepts ... --plan --json`：命令行 / JSON 输出\n"
        "- `docs/DATA_FORMAT.md`：三类专业文件的格式说明"
    ),
]
nb.metadata.kernelspec = {
    "display_name": "Python 3", "language": "python", "name": "python3",
}

from pathlib import Path  # noqa: E402

out = Path(__file__).resolve().parent.parent / "examples/demo.ipynb"
out.parent.mkdir(exist_ok=True)
nbf.write(nb, out)
print(f"written {out}")
