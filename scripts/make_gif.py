# ruff: noqa: E501
"""合成 docs/demo.gif：输入错题 → 根因输出（Wave 2 任务 2.2）。

帧内容全部取自真实命令的真实输出（绝不手造假终端文本）：
  1) head -3 data/demo_attempts.jsonl        —— 输入的作答记录
  2) examdiag diagnose --attempts ... --plan —— 真实子进程 stdout 逐行揭示

渲染：PIL 逐帧画终端风画面（Menlo + PingFang 逐字符回退，解决 CJK），
合成：ffmpeg palettegen/paletteuse 两遍出高质量 GIF；ffmpeg 不可用时退回 PIL 帧动画。

运行：python scripts/make_gif.py   （只读 data/，不改 examdiag/）
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/demo.gif"

BG = (13, 17, 23)
FG = (230, 237, 243)
GREEN = (126, 231, 135)
DIM = (139, 148, 158)
SIZE = 16
LH = 22
PAD = 24
FPS = 12

FONT_LATIN = "/System/Library/Fonts/Menlo.ttc"
FONT_CJK = "/System/Library/Fonts/STHeiti Medium.ttc"


def load_fonts():
    """CJK 字号取 SIZE+4：STHeiti 全角宽 = 字号，20px 正好等于 Menlo 两格（2×10px），
    与 rich 的 "CJK 记 2 格" 宽度约定一致，表格边线才能对齐。"""
    return (
        ImageFont.truetype(FONT_LATIN, SIZE),
        ImageFont.truetype(FONT_CJK, SIZE + 4),
    )


def needs_cjk_font(ch: str) -> bool:
    """真 CJK（含全角标点）用 STHeiti；ASCII 与 box-drawing/箭头留在 Menlo，
    Menlo 的框线字形是 10px 等宽、能无缝拼成表格边。"""
    return ord(ch) >= 0x2E80


def draw_line(draw, xy, text, fonts, fill=FG):
    """逐字符混排：ASCII/制表符用 Menlo，CJK 用 PingFang。"""
    font_l, font_c = fonts
    x, y = xy
    for ch in text:
        f = font_c if needs_cjk_font(ch) else font_l
        draw.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch)


def text_width(text, fonts):
    font_l, font_c = fonts
    return sum(
        (font_c if needs_cjk_font(ch) else font_l).getlength(ch) for ch in text
    )


def run_real() -> tuple[list[str], list[str]]:
    """真实执行两条命令，拿真实输出。"""
    head = subprocess.run(
        ["head", "-3", "data/demo_attempts.jsonl"], cwd=ROOT,
        capture_output=True, text=True, check=True,
    ).stdout.rstrip("\n").split("\n")
    env = dict(os.environ, COLUMNS="104", TERM="dumb")
    diag = subprocess.run(
        ["examdiag", "diagnose", "--attempts", "data/demo_attempts.jsonl",
         "--concepts", "data/concepts/", "--plan"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=True,
    )
    lines = diag.stdout.rstrip("\n").split("\n")
    assert "ds.tree.traverse" in diag.stdout, "真实输出里必须出现验收根因"
    return head, lines


def main() -> None:
    fonts = load_fonts()
    head_lines, diag_lines = run_real()

    cmd = "examdiag diagnose --attempts data/demo_attempts.jsonl --concepts data/concepts/ --plan"
    # 阶段 A：展示输入（真实 head 输出）
    lines_a = [("$ head -3 data/demo_attempts.jsonl", GREEN)]
    lines_a += [(t, DIM) for t in head_lines]
    lines_a += [("", FG), (f"$ {cmd[:0]}", FG)]

    # 帧序列：A 完整显示 4 帧
    frames: list[list[tuple[str, tuple]]] = [lines_a[:-1] + [("", FG)]] * 3

    # 阶段 B：打字机敲命令
    for k in range(1, len(cmd) + 1, 2):
        frames.append(lines_a[:-1] + [(f"$ {cmd[:k]}", FG)])
    frames.append(lines_a[:-1] + [(f"$ {cmd}", FG)])

    # 阶段 C：真实输出逐 2 行揭示（完整命令行保留在顶部）
    base = lines_a[:-1] + [(f"$ {cmd}", FG)]
    for k in range(2, len(diag_lines) + 1, 2):
        frames.append(base + [(t, FG) for t in diag_lines[:k]])
    frames.append(base + [(t, FG) for t in diag_lines])

    # 阶段 D：定格
    frames += [base + [(t, FG) for t in diag_lines]] * 10

    maxw = max(
        int(text_width(t, fonts)) for f in frames for t, _ in f
    ) + PAD * 2
    maxh = max(len(f) for f in frames) * LH + PAD * 2
    print(f"canvas {maxw}x{maxh}, frames={len(frames)}")

    tmp = Path(tempfile.mkdtemp())
    for i, fl in enumerate(frames):
        img = Image.new("RGB", (maxw, maxh), BG)
        d = ImageDraw.Draw(img)
        y = PAD
        for text, color in fl:
            draw_line(d, (PAD, y), text, fonts, color)
            y += LH
        img.save(tmp / f"f{i:04d}.png")

    OUT.parent.mkdir(exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS),
             "-i", str(tmp / "f%04d.png"),
             "-vf", "split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4",
             "-loop", "0", str(OUT)],
            check=True,
        )
        print("assembled with ffmpeg")
    else:  # pragma: no cover
        ims = [Image.open(p) for p in sorted(tmp.glob("f*.png"))]
        ims[0].save(OUT, save_all=True, append_images=ims[1:],
                    duration=int(1000 / FPS), loop=0, optimize=True)
        print("assembled with PIL fallback")
    shutil.rmtree(tmp)
    print(f"written {OUT} ({OUT.stat().st_size / 1024:.0f} KB), frames={len(frames)}, ~{len(frames)/FPS:.1f}s")


if __name__ == "__main__":
    main()
