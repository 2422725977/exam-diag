"""生成 viz/report.html：单文件知识依赖图可视化（无前端框架）。

数据全部来自真实运行：
  - examdiag.diagnose 在 data/demo_attempts.jsonl 上跑出的 mastery 与根因
  - 概念图谱 prereq 边（方向 前置 -> 后继）

布局：按最长前置链分层（Sugiyama 思路的简化版），Python 端算好坐标直接
吐静态 SVG；JS 只负责点击节点 → 右侧详情（涉及错题）与根因面板。
节点颜色按 mastery 渐变：红(0) → 黄(0.5) → 绿(1)，无数据为灰。

运行：python scripts/make_report.py   （不修改 examdiag/ 与 data/ 的任何文件）
"""

# ruff: noqa: E501  — 文件内嵌 HTML/JS 模板，行宽不受 100 限制

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from examdiag.diagnose import diagnose
from examdiag.graph import build, topo_order
from examdiag.schema import load_attempts, load_concepts, load_questions

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "viz/report.html"

NODE_W, NODE_H = 152, 44
COL_GAP, ROW_GAP = 46, 18
MARGIN = 46


def lerp_color(t: float) -> str:
    """mastery 0..1 → 红→黄→绿 渐变。"""
    stops = [(220, 38, 38), (245, 158, 11), (22, 163, 74)]
    seg = min(max(t, 0.0), 1.0) * 2
    i = min(int(seg), 1)
    f = seg - i
    c0, c1 = stops[i], stops[i + 1]
    rgb = tuple(int(a + (b - a) * f) for a, b in zip(c0, c1, strict=True))
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def main() -> None:
    concepts = load_concepts(ROOT / "data/concepts/408.yaml")
    questions = load_questions(ROOT / "data/questions/408.jsonl")
    attempts = load_attempts(ROOT / "data/demo_attempts.jsonl")
    diag = diagnose(attempts, questions, concepts)
    g = build(concepts)

    qmap = {q.id: q for q in questions}
    stats: dict[str, dict] = {}
    for cid in concepts.concepts:
        rows = [a for a in attempts if cid in qmap[a.question_id].concepts]
        wrong_qs, seen = [], set()
        for a in rows:
            if not a.correct and a.question_id not in seen:
                seen.add(a.question_id)
                stem = qmap[a.question_id].stem.replace("\n", " ")[:38]
                wrong_qs.append([a.question_id, stem])
        stats[cid] = {
            "name": concepts.concepts[cid].name,
            "attempts": len(rows),
            "correct": sum(a.correct for a in rows),
            "wrong_questions": wrong_qs,
            "mastery": diag.mastery.get(cid),
        }

    # 分层布局：最长前置链定层，层内按 id 排序
    depth: dict[str, int] = {}
    for cid in topo_order(g):
        ps = concepts.concepts[cid].prereqs
        depth[cid] = 1 + max((depth[p] for p in ps), default=0)
    layers: dict[int, list[str]] = defaultdict(list)
    for cid, d in depth.items():
        layers[d].append(cid)
    pos: dict[str, tuple[float, float]] = {}
    for d in sorted(layers):
        col = layers[d]
        for i, cid in enumerate(sorted(col)):
            pos[cid] = (
                MARGIN + d * (NODE_W + COL_GAP),
                MARGIN + i * (NODE_H + ROW_GAP),
            )
    n_layers = max(layers) + 1
    max_col = max(len(c) for c in layers.values())
    W = MARGIN * 2 + n_layers * (NODE_W + COL_GAP) - COL_GAP
    H = MARGIN * 2 + max_col * (NODE_H + ROW_GAP) - ROW_GAP

    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    svg_edges = []
    path_edges = set()
    for r in diag.root_causes:
        for a, b in zip(r.remedy_path, r.remedy_path[1:], strict=False):
            path_edges.add((a, b))
    for u, v in g.edges:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        mx = (x0 + NODE_W + x1) / 2
        d = f"M {x0 + NODE_W:.0f} {y0 + NODE_H / 2:.0f} C {mx:.0f} {y0 + NODE_H / 2:.0f}, {mx:.0f} {y1 + NODE_H / 2:.0f}, {x1:.0f} {y1 + NODE_H / 2:.0f}"
        hot = (u, v) in path_edges
        svg_edges.append(
            f'<path class="edge{" hot" if hot else ""}" data-u="{u}" data-v="{v}" d="{d}"/>'
        )

    svg_nodes = []
    for cid, (x, y) in pos.items():
        s = stats[cid]
        m = s["mastery"]
        color = lerp_color(m) if m is not None else "#94a3b8"
        label = esc(s["name"])[:9]
        svg_nodes.append(
            f'<g class="node" data-id="{cid}" transform="translate({x:.0f},{y:.0f})">'
            f'<rect width="{NODE_W}" height="{NODE_H}" rx="10" fill="{color}" fill-opacity="0.92"/>'
            f'<text x="10" y="19" class="nname">{label}</text>'
            f'<text x="10" y="35" class="nid">{esc(cid)[:20]}</text></g>'
        )

    causes = [r.to_dict() for r in diag.root_causes]
    data = {
        "stats": stats,
        "causes": causes,
        "names": {cid: c.name for cid, c in concepts.concepts.items()},
        "prereqs": {cid: c.prereqs for cid, c in concepts.concepts.items()},
    }

    html = TEMPLATE.replace("%DATA%", json.dumps(data, ensure_ascii=False))
    html = html.replace("%W%", str(W + 340)).replace("%GW%", str(W))
    html = html.replace("%H%", str(H + 150))
    html = html.replace("%EDGES%", "\n".join(svg_edges))
    html = html.replace("%NODES%", "\n".join(svg_nodes))
    html = html.replace("%NC%", str(len(pos)))
    html = html.replace("%NE%", str(len(g.edges)))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"written {OUT} ({OUT.stat().st_size / 1024:.0f} KB), "
          f"nodes={len(pos)} edges={len(g.edges)} causes={[r.concept_id for r in diag.root_causes]}")


TEMPLATE = """<!doctype html>
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
  #wrap { display:flex; }
  #graph { width:%GW%px; overflow:auto; padding:8px; }
  #side { width:320px; padding:14px; border-left:1px solid #1f2a3c; }
  .edge { stroke:#31446b; stroke-width:1.4; fill:none; }
  .edge.hot { stroke:#7ee787; stroke-width:2.6; }
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
  <div class="cmd">$ examdiag diagnose --attempts data/demo_attempts.jsonl --concepts data/concepts/</div>
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
      <small>颜色 = 掌握度（红 0 → 黄 0.5 → 绿 1，灰 = 无作答数据）；
      绿色加粗路径 = 根因补习路径</small></div>
    <div id="causes"></div>
  </div>
</div>
<script>
const DATA = %DATA%;
const svg = document.querySelector('svg');
const panel = document.getElementById('panel');

function fmtM(m){ return m === null ? '无数据' : (Math.round(m*100)/100).toFixed(2); }

svg.querySelectorAll('.node').forEach(n => {
  n.addEventListener('click', () => {
    svg.querySelectorAll('.node').forEach(x => x.classList.remove('sel'));
    svg.querySelectorAll('.edge').forEach(x => x.classList.remove('hot2'));
    n.classList.add('sel');
    const id = n.dataset.id, s = DATA.stats[id];
    svg.querySelectorAll('.edge').forEach(e => {
      if (e.dataset.u === id || e.dataset.v === id) e.classList.add('hot2');
    });
    const m = s.mastery;
    const bar = m === null ? '' :
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

// 默认选中第一个根因
const first = DATA.causes[0] && DATA.causes[0].concept_id;
if (first) document.querySelector(`.node[data-id="${first}"]`).dispatchEvent(new Event('click'));
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
