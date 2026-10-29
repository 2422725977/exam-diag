# ruff: noqa: E501  — 内嵌 HTML 模板行超宽
"""诊断报告导出模块：Markdown / CSV / Excel(xlsx) / 单文件 HTML。

HTML 渲染由 scripts/make_report.py 下沉而来（分层布局 + mastery 渐变 +
点击查错题），脚本退化为薄包装。导出函数全部以 diagnose.Diagnosis 为输入，
面向三类消费场景：
  - export_markdown：人读报告（进笔记/归档）
  - export_mapping_csv / export_xlsx：错题→根因→补救练习 映射表（进表格软件）
  - write_html：交互式可视化（浏览器打开）
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .diagnose import Diagnosis
from .graph import build, topo_order
from .schema import Attempt, ConceptGraph, Question
from .srs import plan_week

NODE_W, NODE_H = 152, 44
COL_GAP, ROW_GAP = 46, 18
MARGIN = 46
STEM_HEAD = 38


def lerp_color(t: float) -> str:
    """mastery 0..1 → 红→黄→绿 渐变的十六进制色。"""
    stops = [(220, 38, 38), (245, 158, 11), (22, 163, 74)]
    seg = min(max(t, 0.0), 1.0) * 2
    i = min(int(seg), 1)
    f = seg - i
    c0, c1 = stops[i], stops[i + 1]
    rgb = tuple(int(a + (b - a) * f) for a, b in zip(c0, c1, strict=True))
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def collect_stats(
    attempts: list[Attempt], questions: list[Question], concepts: ConceptGraph
) -> dict[str, dict]:
    """逐概念统计：作答数、正确数、掌握度、涉及错题（编号 + 题干摘要）。"""
    qmap = {q.id: q for q in questions}
    stats: dict[str, dict] = {}
    for cid in concepts.concepts:
        rows = [a for a in attempts if cid in qmap[a.question_id].concepts]
        wrong_qs, seen = [], set()
        for a in rows:
            if not a.correct and a.question_id not in seen:
                seen.add(a.question_id)
                stem = qmap[a.question_id].stem.replace("\n", " ")[:STEM_HEAD]
                wrong_qs.append([a.question_id, stem])
        stats[cid] = {
            "name": concepts.concepts[cid].name,
            "attempts": len(rows),
            "correct": sum(a.correct for a in rows),
            "wrong_questions": wrong_qs,
        }
    return stats


def layered_layout(concepts: ConceptGraph) -> tuple[dict[str, tuple[float, float]], int, int, int]:
    """最长前置链分层布局：返回 (坐标, 画布宽, 画布高, 层数)。"""
    g = build(concepts)
    depth: dict[str, int] = {}
    for cid in topo_order(g):
        depth[cid] = 1 + max((depth[p] for p in g.predecessors(cid)), default=0)
    layers: dict[int, list[str]] = defaultdict(list)
    for cid, d in depth.items():
        layers[d].append(cid)
    pos: dict[str, tuple[float, float]] = {}
    for d in sorted(layers):
        for i, cid in enumerate(sorted(layers[d])):
            pos[cid] = (
                MARGIN + d * (NODE_W + COL_GAP),
                MARGIN + i * (NODE_H + ROW_GAP),
            )
    n_layers = max(layers) + 1
    max_col = max(len(c) for c in layers.values())
    w = MARGIN * 2 + n_layers * (NODE_W + COL_GAP) - COL_GAP
    h = MARGIN * 2 + max_col * (NODE_H + ROW_GAP) - ROW_GAP
    return pos, w, h, n_layers


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(
    diagnosis: Diagnosis,
    concepts: ConceptGraph,
    stats: dict[str, dict],
    cmd_line: str = "",
) -> str:
    """渲染单文件 HTML（内嵌 JSON 数据 + 静态 SVG + 原生 JS 交互）。"""
    g = build(concepts)
    pos, W, H, _ = layered_layout(concepts)

    svg_edges, svg_nodes = [], []
    path_edges = set()
    for r in diagnosis.root_causes:
        for a, b in zip(r.remedy_path, r.remedy_path[1:], strict=False):
            path_edges.add((a, b))
    for u, v in g.edges:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        mx = (x0 + NODE_W + x1) / 2
        d = (
            f"M {x0 + NODE_W:.0f} {y0 + NODE_H / 2:.0f} "
            f"C {mx:.0f} {y0 + NODE_H / 2:.0f}, "
            f"{mx:.0f} {y1 + NODE_H / 2:.0f}, {x1:.0f} {y1 + NODE_H / 2:.0f}"
        )
        hot = (u, v) in path_edges
        svg_edges.append(
            f'<path class="edge{" hot" if hot else ""}" data-u="{u}" data-v="{v}" d="{d}"/>'
        )
    for cid, (x, y) in pos.items():
        s = stats[cid]
        m = diagnosis.mastery.get(cid)
        color = lerp_color(m) if m is not None else "#94a3b8"
        svg_nodes.append(
            f'<g class="node" data-id="{cid}" transform="translate({x:.0f},{y:.0f})">'
            f'<rect width="{NODE_W}" height="{NODE_H}" rx="10" fill="{color}" fill-opacity="0.92"/>'
            f'<text x="10" y="19" class="nname">{_esc(s["name"])[:9]}</text>'
            f'<text x="10" y="35" class="nid">{_esc(cid)[:20]}</text></g>'
        )


    data = {
        "stats": [
            {
                "id": cid,
                "name": s["name"],
                "attempts": s["attempts"],
                "correct": s["correct"],
                "wrong_questions": s["wrong_questions"],
                "mastery": diagnosis.mastery.get(cid),
            }
            for cid, s in stats.items()
        ],
        "causes": [r.to_dict() for r in diagnosis.root_causes],
        "names": {cid: c.name for cid, c in concepts.concepts.items()},
        "prereqs": {cid: c.prereqs for cid, c in concepts.concepts.items()},
    }
    html = HTML_TEMPLATE
    html = html.replace("%DATA%", _to_json(data))
    html = html.replace("%W%", str(W + 340)).replace("%GW%", str(W))
    html = html.replace("%H%", str(H + 150))
    html = html.replace("%EDGES%", "\n".join(svg_edges))
    html = html.replace("%NODES%", "\n".join(svg_nodes))
    html = html.replace("%NC%", str(len(pos)))
    html = html.replace("%NE%", str(len(g.edges)))
    html = html.replace("%CMD%", _esc(cmd_line))
    html = html.replace("%GEN%", datetime.now().strftime("%Y-%m-%d %H:%M"))
    return html


def _to_json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def write_html(
    diagnosis: Diagnosis,
    concepts: ConceptGraph,
    attempts: list[Attempt],
    questions: list[Question],
    out_path: str | Path,
    cmd_line: str = "",
) -> Path:
    """一站式 HTML 导出：统计 + 渲染 + 落盘。"""
    stats = collect_stats(attempts, questions, concepts)
    html = render_html(diagnosis, concepts, stats, cmd_line)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def _remedy_names(concepts: ConceptGraph, path: list[str]) -> str:
    return " → ".join(concepts.concepts[c].name for c in path)


def _root_for(concept_id: str, diagnosis: Diagnosis) -> str:
    """该概念归属哪个根因（根因自身或其 explains 命中）；无归属返回 —。"""
    for r in diagnosis.root_causes:
        if concept_id == r.concept_id or concept_id in r.explains:
            return f"{r.name}({r.concept_id})"
    return "—"


def export_mapping(
    diagnosis: Diagnosis,
    concepts: ConceptGraph,
    attempts: list[Attempt],
    questions: list[Question],
    user_id: str | None = None,
) -> list[dict]:
    """错题→根因概念→补救练习 映射表行（CSV/Excel 共用）。"""
    qmap = {q.id: q for q in questions}
    rows = [a for a in attempts if a.user_id == user_id] if user_id else list(attempts)
    out = []
    for a in sorted(rows, key=lambda x: x.ts):
        if a.correct:
            continue
        q = qmap[a.question_id]
        primary = q.concepts[0]
        m = diagnosis.mastery.get(primary)
        out.append(
            {
                "用户": a.user_id,
                "时间": a.ts.strftime("%Y-%m-%d %H:%M"),
                "题目": q.id,
                "题干摘要": q.stem.replace("\n", " ")[:STEM_HEAD],
                "正确答案": q.answer,
                "主概念": f"{concepts.concepts[primary].name}({primary})",
                "主概念掌握度": "无数据" if m is None else f"{m:.2f}",
                "归属根因": _root_for(primary, diagnosis),
                "补救练习": _remedy_names(concepts, diagnosis.root_causes[0].remedy_path)
                if diagnosis.root_causes
                else "—",
            }
        )
    return out


def export_mapping_csv(
    diagnosis: Diagnosis,
    concepts: ConceptGraph,
    attempts: list[Attempt],
    questions: list[Question],
    out_path: str | Path,
    user_id: str | None = None,
) -> Path:
    """映射表导出为 CSV（utf-8-sig，Excel 直接打开中文不乱码）。"""
    rows = export_mapping(diagnosis, concepts, attempts, questions, user_id)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["用户", "时间", "题目", "题干摘要", "正确答案",
                                         "主概念", "主概念掌握度", "归属根因", "补救练习"]
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return out


def export_xlsx(
    diagnosis: Diagnosis,
    concepts: ConceptGraph,
    attempts: list[Attempt],
    questions: list[Question],
    out_path: str | Path,
    user_id: str | None = None,
) -> Path:
    """三工作表 xlsx：根因汇总 / 错题映射 / 7天计划（openpyxl）。"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    header_fill = PatternFill("solid", fgColor="E8EDF3")
    bold = Font(bold=True)

    ws = wb.active
    ws.title = "根因汇总"
    ws.append(["#", "根因概念", "id", "掌握度", "涉及错题", "补习路径", "解释的下游症状"])
    for c in ws[1]:
        c.font, c.fill = bold, header_fill
    for i, r in enumerate(diagnosis.root_causes, 1):
        ws.append([
            i, r.name, r.concept_id, round(r.mastery, 2), r.wrong_count,
            _remedy_names(concepts, r.remedy_path),
            "、".join(concepts.concepts[c].name for c in r.explains) or "—",
        ])
    for col, w in zip("ABCDEFG", (5, 22, 24, 10, 10, 46, 40), strict=True):
        ws.column_dimensions[col].width = w

    ws2 = wb.create_sheet("错题映射")
    rows = export_mapping(diagnosis, concepts, attempts, questions, user_id)
    fields = (
        list(rows[0]) if rows
        else ["用户", "时间", "题目", "题干摘要", "正确答案", "主概念",
              "主概念掌握度", "归属根因", "补救练习"]
    )
    ws2.append(fields)
    for c in ws2[1]:
        c.font, c.fill = bold, header_fill
    for r in rows:
        ws2.append([r[f] for f in fields])
    for col in range(1, len(fields) + 1):
        ws2.column_dimensions[get_column_letter(col)].width = 20

    ws3 = wb.create_sheet("7天计划")
    ws3.append(["天", "复习概念（最弱优先）"])
    for c in ws3[1]:
        c.font, c.fill = bold, header_fill
    for p in plan_week(diagnosis):
        names = "、".join(concepts.concepts[c].name for c in p.concepts) or "（休息）"
        ws3.append([f"Day {p.day}", names])
    ws3.column_dimensions["A"].width = 10
    ws3.column_dimensions["B"].width = 60

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def export_markdown(
    diagnosis: Diagnosis,
    concepts: ConceptGraph,
    out_path: str | Path,
    title: str = "根因诊断报告",
) -> Path:
    """人读 Markdown 报告：根因表 + 逐根因详情 + insufficient + 7 天计划。"""
    lines = [
        f"# {title}",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 诊断用户：{diagnosis.user_id or '（全部用户合并）'}",
        "",
        "## 根因",
        "",
        "| # | 根因概念 | 掌握度 | 涉及错题 | 补习路径 |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(diagnosis.root_causes, 1):
        lines.append(
            f"| {i} | {r.name} `{r.concept_id}` | {r.mastery:.2f} | {r.wrong_count} "
            f"| {_remedy_names(concepts, r.remedy_path)} |"
        )
    for i, r in enumerate(diagnosis.root_causes, 1):
        lines += [
            "",
            f"### #{i} {r.name}",
            "",
            f"- 掌握度 {r.mastery:.2f}，涉及错题 {r.wrong_count}，图距离 {r.min_distance}",
            f"- 补习路径：{_remedy_names(concepts, r.remedy_path)}",
            f"- 解释的下游症状：{'、'.join(concepts.concepts[c].name for c in r.explains) or '—'}",
        ]
    if diagnosis.insufficient_data:
        lines += ["", "## insufficient_data（作答 < 3 次，不下结论）", "",
                  "、".join(diagnosis.insufficient_data)]
    lines += ["", "## 未来 7 天复习计划", ""]
    for p in plan_week(diagnosis):
        names = "、".join(concepts.concepts[c].name for c in p.concepts) or "（休息）"
        lines.append(f"- **Day {p.day}**：{names}")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>exam-diag 根因可视化报告</title>
<style>
  body { margin:0; background:#0b1220; color:#e6edf3;
         font-family:"PingFang SC","Hiragino Sans GB",sans-serif; }
  header { padding:14px 20px; border-bottom:1px solid #1f2a3c; }
  header h1 { font-size:18px; margin:0 0 4px; }
  header .cmd { font-family:Menlo,monospace; font-size:12px; color:#7ee787; }
  header .gen { font-family:Menlo,monospace; font-size:11px; color:#8b98ab; }
  #wrap { display:flex; }
  #graph { width:%GW%px; overflow:auto; padding:8px; }
  #side { width:320px; padding:14px; border-left:1px solid #1f2a3c; }
  .edge { stroke:#31446b; stroke-width:1.4; fill:none; }
  .edge.hot { stroke:#7ee787; stroke-width:2.6; }
  .edge.hot2 { stroke:#f0f6fc; stroke-width:2; }
  .node { cursor:pointer; }
  .node:hover rect { stroke:#fff; stroke-width:2; }
  .node.sel rect { stroke:#7ee787; stroke-width:2.6; }
  .nname { fill:#0b1220; font-size:12px; font-weight:600; }
  .nid   { fill:#0b1220; font-size:10px; opacity:.75; font-family:Menlo,monospace; }
  #panel h2, #side h3 { font-size:14px; margin:6px 0; }
  #panel .m { font-family:Menlo,monospace; }
  ul { padding-left:18px; margin:6px 0; } li { font-size:12px; line-height:1.5; }
  .bar { height:8px; border-radius:4px; background:#1f2a3c; margin:6px 0; }
  .bar i { display:block; height:8px; border-radius:4px; }
  .card { background:#111a2c; border:1px solid #1f2a3c; border-radius:8px;
          padding:10px; margin-bottom:10px; }
  small { color:#8b98ab; }
</style>
</head>
<body>
<header>
  <h1>exam-diag 根因可视化报告（%NC% 概念 / %NE% 依赖边）</h1>
  <div class="cmd">$ %CMD%</div>
  <div class="gen">生成于 %GEN% · 节点颜色 = 掌握度（红 0 → 黄 0.5 → 绿 1，灰 = 无数据）</div>
</header>
<div id="wrap">
  <div id="graph">
    <svg width="%GW%" height="%H%" viewBox="0 0 %GW% %H%">
      %EDGES%
      %NODES%
    </svg>
  </div>
  <div id="side">
    <div id="panel" class="card"><h2>点击任意概念节点查看详情</h2>
      <small>绿色加粗路径 = 根因补习路径</small></div>
    <div id="causes"></div>
  </div>
</div>
<script>
const DATA = %DATA%;
const svg = document.querySelector('svg');
const panel = document.getElementById('panel');
const byId = {};
DATA.stats.forEach(s => byId[s.id] = s);

function fmtM(m){ return m === null || m === undefined ? '无数据' : (Math.round(m*100)/100).toFixed(2); }

svg.querySelectorAll('.node').forEach(n => {
  n.addEventListener('click', () => {
    svg.querySelectorAll('.node').forEach(x => x.classList.remove('sel'));
    svg.querySelectorAll('.edge').forEach(x => x.classList.remove('hot2'));
    n.classList.add('sel');
    const id = n.dataset.id, s = byId[id];
    svg.querySelectorAll('.edge').forEach(e => {
      if (e.dataset.u === id || e.dataset.v === id) e.classList.add('hot2');
    });
    const m = s.mastery;
    const bar = (m === null || m === undefined) ? '' :
      `<div class="bar"><i style="width:${Math.round(m*100)}%;background:${m<0.4?'#dc2626':m<0.7?'#f59e0b':'#16a34a'}"></i></div>`;
    const wq = s.wrong_questions.length
      ? '<ul>' + s.wrong_questions.map(w => `<li><span class="m">${w[0]}</span> ${w[1]}…</li>`).join('') + '</ul>'
      : '<small>无涉及错题</small>';
    const pre = DATA.prereqs[id].map(p => DATA.names[p] + ' (' + p + ')').join('、') || '无（根节点）';
    panel.innerHTML = `<h2>${s.name} <small>${id}</small></h2>`
      + `掌握度：${fmtM(m)}　作答 ${s.attempts} 次 / 对 ${s.correct}${bar}`
      + `<h3>前置概念</h3><small>${pre}</small>`
      + `<h3>涉及错题（${s.wrong_questions.length}）</h3>${wq}`;
  });
});

const c = document.getElementById('causes');
c.innerHTML = '<h3>根因 Top' + DATA.causes.length + '</h3>' + DATA.causes.map((r,i) =>
  `<div class="card"><b>#${i+1} ${r.name}</b> <small>${r.concept_id}</small>`
  + `<div class="m">mastery=${fmtM(r.mastery)} 错题=${r.wrong_count}</div>`
  + `<small>补习路径：${r.remedy_path.map(p=>DATA.names[p]).join(' → ')}</small>`
  + `<br><small>解释症状：${r.explains.map(p=>DATA.names[p]).join('、') || '—'}</small></div>`
).join('');

const first = DATA.causes[0] && DATA.causes[0].concept_id;
if (first) document.querySelector(`.node[data-id="${first}"]`).dispatchEvent(new Event('click'));
</script>
</body>
</html>
"""
