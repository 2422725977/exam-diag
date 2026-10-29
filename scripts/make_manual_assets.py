# ruff: noqa: E501
"""软著说明书截图（Wave 4 任务 4.2a）：全部来自真实运行，禁止示意。

终端类截图（PIL 终端风渲染，帧文本 = 真实子进程 stdout，与 docs/demo.gif 同标准）：
  assets/shot_install.png    pip install -e . + pytest tests/ -q   （安装与自检）
  assets/shot_bkt_fit.png    合成数据 EM 拟合与参数恢复误差（BKT 模块）
  assets/shot_diagnose.png   examdiag diagnose --user demo-a       （诊断模块）
  assets/shot_remedy.png     三个用户的补习路径（API 真实输出）
  assets/shot_validate.png   python scripts/validate_data.py all   （数据校验模块）
可视化截图 assets/shot_viz.png 由浏览器实截 viz/report.html（scripts/shot_viz_browser.js）。

运行：python scripts/make_manual_assets.py
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs/copyright/assets"

BG = (13, 17, 23)
FG = (230, 237, 243)
GREEN = (126, 231, 135)
SIZE = 16
SIZE_CJK = 20
LH = 24
PAD = 22
FONT_LATIN = "/System/Library/Fonts/Menlo.ttc"
FONT_CJK = "/System/Library/Fonts/STHeiti Medium.ttc"


def load_fonts():
    return ImageFont.truetype(FONT_LATIN, SIZE), ImageFont.truetype(FONT_CJK, SIZE_CJK)


def draw_line(draw, x, y, text, fonts, fill=FG):
    fl, fc = fonts
    for ch in text:
        f = fc if ord(ch) >= 0x2E80 else fl
        draw.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch)


def render_terminal(title: str, lines: list[tuple[str, str]], out: Path) -> None:
    """lines: (text, color)；首行为命令提示（绿色）。"""
    fonts = load_fonts()
    tmp = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(tmp)
    maxw = max(
        int(sum((fonts[1] if ord(c) >= 0x2E80 else fonts[0]).getlength(c) for c in t))
        for t, _ in lines
    )
    W = min(max(maxw + PAD * 2, 700), 1500)
    H = len(lines) * LH + PAD * 2 + 30
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    draw_line(d, PAD, 8, title, fonts, (120, 130, 145))
    y = 30
    for text, color in lines:
        draw_line(d, PAD, y, text, fonts, color)
        y += LH
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"saved {out} ({W}x{H})")


def run_capture(cmd: list[str], env_cols: str | None = "100") -> list[str]:
    env = dict(os.environ)
    if env_cols:
        env["COLUMNS"] = env_cols
        env["TERM"] = "dumb"
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    return proc.stdout.rstrip("\n").split("\n")


def green(cmd: str) -> tuple[str, str]:
    return ("$ " + cmd, GREEN)


def main() -> None:
    # 1) 安装与自检
    install_lines = [green("pip install -e .")]
    install_lines += [("Successfully installed exam-diag-0.1.0", FG)]  # 占位，下面用真实输出
    # 真实执行：安装（幂等）+ pytest
    real_install = run_capture(["pip", "install", "-e", "."])
    real_test = run_capture(["python", "-m", "pytest", "tests/", "-q"])
    install_lines = (
        [green("pip install -e .")]
        + [(t, FG) for t in real_install if t.strip()][-2:]
        + [green("python -m pytest tests/ -q")]
        + [(t, FG) for t in real_test]
    )
    render_terminal("安装与测试自检（真实执行）", install_lines, ASSETS / "shot_install.png")

    # 2) BKT 拟合（真实运行内联脚本）
    fit_script = textwrap.dedent("""
        import numpy as np
        from examdiag.bkt import BKTParams, fit, simulate
        TRUE = BKTParams(p_L0=0.3, p_T=0.1, p_S=0.1, p_G=0.2)
        seqs = list(simulate(TRUE, n_students=2000, seq_len=30, seed=42))
        fitted = fit(seqs, init=BKTParams(p_L0=0.4, p_T=0.15, p_S=0.15, p_G=0.15))
        print("true   :", TRUE.as_array().round(4).tolist())
        print("fitted :", fitted.as_array().round(4).tolist())
        print("abs err:", np.abs(fitted.as_array() - TRUE.as_array()).round(4).tolist())
    """).strip()
    out = run_capture(["python", "-c", fit_script])
    render_terminal(
        "BKT EM 拟合（2000 条合成序列，真实输出）",
        [green("python -c \"fit on 2000 synthetic sequences\"")] + [(t, FG) for t in out],
        ASSETS / "shot_bkt_fit.png",
    )

    # 3) 诊断（demo-a，真实 CLI 子进程）
    diag = run_capture([
        "examdiag", "diagnose", "--attempts", "data/demo_attempts_multi.jsonl",
        "--concepts", "data/concepts/", "--user", "demo-a",
    ])
    render_terminal(
        "examdiag diagnose --user demo-a（真实输出）",
        [green("examdiag diagnose --attempts data/demo_attempts_multi.jsonl "
               "--concepts data/concepts/ --user demo-a")]
        + [(t, FG) for t in diag if t.strip()],
        ASSETS / "shot_diagnose.png",
    )

    # 4) 补习路径（三个用户，真实 API 输出）
    remedy_script = textwrap.dedent("""
        from examdiag.diagnose import diagnose
        from examdiag.schema import ConceptGraph, load_attempts, load_concepts, load_questions
        merged = {}
        for f in ("408", "math1"):
            merged.update(load_concepts(f"data/concepts/{f}.yaml").concepts)
        concepts = ConceptGraph(concepts=merged)
        questions = (load_questions("data/questions/408.jsonl")
                     + load_questions("data/questions/math1.jsonl"))
        attempts = load_attempts("data/demo_attempts_multi.jsonl")
        for u in ("demo-a", "demo-b", "demo-c"):
            d = diagnose(attempts, questions, concepts, user_id=u)
            r = d.root_causes[0]
            path = " -> ".join(concepts.concepts[c].name for c in r.remedy_path)
            print(f"{u}: 根因 {r.name}({r.concept_id}) mastery={r.mastery:.2f}")
            print(f"   补习路径: {path}")
    """).strip()
    out = run_capture(["python", "-c", remedy_script])
    render_terminal(
        "补习路径输出（三个用户，真实运行）",
        [green("python -c \"print remedy paths for demo-a/b/c\"")] + [(t, FG) for t in out],
        ASSETS / "shot_remedy.png",
    )

    # 4.5) 版本自报家门（名称/版本证据闭环）
    ver = run_capture(["examdiag", "--version"])
    render_terminal(
        "examdiag --version（真实输出）",
        [green("examdiag --version")] + [(t, FG) for t in ver],
        ASSETS / "shot_version.png",
    )

    # 5) 数据校验（真实全量校验）
    val = run_capture(["python", "scripts/validate_data.py", "all"], env_cols="110")
    render_terminal(
        "python scripts/validate_data.py all（真实输出）",
        [green("python scripts/validate_data.py all")] + [(t, FG) for t in val],
        ASSETS / "shot_validate.png",
    )


if __name__ == "__main__":
    main()
