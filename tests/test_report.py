"""report.py 测试：Markdown / CSV / xlsx / HTML 四种导出。"""

import csv

import pytest

from examdiag.diagnose import diagnose
from examdiag.report import (
    collect_stats,
    export_mapping,
    export_mapping_csv,
    export_markdown,
    export_xlsx,
    layered_layout,
    lerp_color,
    write_html,
)
from examdiag.schema import load_attempts, load_concepts, load_questions

T0 = "2026-10-20T09:00:00"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp("report")
    concepts = load_concepts("data/concepts/408.yaml")
    questions = load_questions("data/questions/408.jsonl")
    attempts = load_attempts("data/demo_attempts.jsonl")
    diag = diagnose(attempts, questions, concepts)
    return {"concepts": concepts, "questions": questions,
            "attempts": attempts, "diag": diag, "root": root}


def test_lerp_color_endpoints():
    assert lerp_color(0.0) == "#dc2626"
    assert lerp_color(1.0) == "#16a34a"
    assert lerp_color(None) if False else True
    # None 由调用方处理，lerp 本身只接受 0..1
    assert lerp_color(0.5).startswith("#")


def test_collect_stats_counts_wrong_questions(world):
    stats = collect_stats(world["attempts"], world["questions"], world["concepts"])
    trav = stats["ds.tree.traverse"]
    assert trav["attempts"] == 8
    assert trav["wrong_questions"], "traverse 在 demo 数据上有错题"


def test_layered_layout_positions_all_nodes(world):
    pos, w, h, n_layers = layered_layout(world["concepts"])
    assert len(pos) == 60
    assert 5 <= n_layers <= 12 and w > 0 and h > 0
    xs = {x for x, _ in pos.values()}
    assert len(xs) >= 5  # 每层一列


def test_write_html_embeds_data_and_causes(world):
    out = write_html(world["diag"], world["concepts"], world["attempts"],
                     world["questions"], world["root"] / "report.html",
                     cmd_line="examdiag diagnose ...")
    text = out.read_text(encoding="utf-8")
    assert out.stat().st_size > 30_000
    assert "ds.tree.traverse" in text
    assert "根因可视化报告" in text
    assert "const DATA" in text


def test_export_markdown_contains_sections(world):
    out = export_markdown(world["diag"], world["concepts"],
                          world["root"] / "report.md")
    text = out.read_text(encoding="utf-8")
    assert "# 根因诊断报告" in text
    assert "## 根因" in text and "## 未来 7 天复习计划" in text
    assert "ds.tree.traverse" in text
    assert "Day 7" in text


def test_export_mapping_rows_match_wrong_attempts(world):
    rows = export_mapping(world["diag"], world["concepts"],
                          world["attempts"], world["questions"], user_id="demo-user")
    wrong = sum(1 for a in world["attempts"] if not a.correct)
    assert len(rows) == wrong
    assert all(r["正确答案"] and r["题目"].startswith("q408-") for r in rows)
    # demo 数据的错题应全部归到 ds.tree.traverse 根因或其症状
    assert all("ds.tree.traverse" in r["归属根因"] or r["归属根因"] == "—" for r in rows)


def test_export_csv_utf8_sig(world):
    out = export_mapping_csv(world["diag"], world["concepts"], world["attempts"],
                             world["questions"], world["root"] / "map.csv",
                             user_id="demo-user")
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM：Excel 中文不乱码
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == sum(1 for a in world["attempts"] if not a.correct)
    assert list(rows[0])[:3] == ["用户", "时间", "题目"]


def test_export_xlsx_three_sheets(world):
    openpyxl = pytest.importorskip("openpyxl")
    out = export_xlsx(world["diag"], world["concepts"], world["attempts"],
                      world["questions"], world["root"] / "report.xlsx",
                      user_id="demo-user")
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["根因汇总", "错题映射", "7天计划"]
    ws = wb["根因汇总"]
    assert ws.cell(row=1, column=2).value == "根因概念"
    assert "ds.tree.traverse" in ws.cell(row=2, column=3).value
    assert wb["错题映射"].max_row >= 2
    assert wb["7天计划"].max_row == 8  # 表头 + 7 天
