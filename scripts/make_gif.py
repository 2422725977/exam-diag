# ruff: noqa: E501
"""合成 docs/demo.gif：三个用户、三条不同方向的薄弱链 → 三个不同根因。

帧内容全部取自真实子进程输出（绝不手造假终端文本）：
  $ examdiag diagnose --attempts data/demo_attempts_multi.jsonl \
        --concepts data/concepts/ --user demo-a   → 根因 = ds.tree.traverse
  $ ... --user demo-b                             → 根因 = os.process.sched (+死锁)
  $ ... --user demo-c                             → 根因 = math.prob.expectation

终端不清屏，三段依次追加，最后一屏同时呈现 3 个不同根因。
规格：12 fps、总帧数 120-144（10-12 s）、表格完整出现后静止 ≥36 帧（≥3 s）。
渲染 PIL（Menlo + STHeiti 逐字符回退，CJK 按 2 格宽对齐），合成 ffmpeg palette。

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
SIZE = 16
LH = 22
PAD = 24
FPS = 12
USERS = ("demo-a", "demo-b", "demo-c")
EXPECTED_ROOT = {
    "demo-a": "ds.tree.traverse",
    "demo-b": "os.process.sched",
    "demo-c": "math.prob.expectation",
}

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
    font_l, font_c = fonts
    x, y = xy
    for ch in text:
        f = font_c if needs_cjk_font(ch) else font_l
        draw.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch)


def text_width(text, fonts):
    font_l, font_c = fonts
    return sum((font_c if needs_cjk_font(ch) else font_l).getlength(ch) for ch in text)


def run_real(user: str) -> list[str]:
    """真实执行 diagnose 子进程，返回 stdout 行；断言预期根因出现在输出里。"""
    env = dict(os.environ, COLUMNS="96", TERM="dumb")
    proc = subprocess.run(
        ["examdiag", "diagnose", "--attempts", "data/demo_attempts_multi.jsonl",
         "--concepts", "data/concepts/", "--user", user],
        cwd=ROOT, env=env, capture_output=True, text=True, check=True,
    )
    lines = proc.stdout.rstrip("\n").split("\n")
    expected = EXPECTED_ROOT[user]
    assert expected in proc.stdout, f"{user} 的真实输出里必须出现根因 {expected}"
    return lines


def build_frames(fonts) -> list[list[tuple[str, tuple]]]:
    frames: list[list[tuple[str, tuple]]] = []
    terminal: list[tuple[str, tuple]] = []
    type_step, reveal_step = 5, 2

    for idx, user in enumerate(USERS):
        out = run_real(user)
        cmd = (f"examdiag diagnose --attempts data/demo_attempts_multi.jsonl "
               f"--concepts data/concepts/ --user {user}")
        base = [*terminal, ("$ " + cmd, GREEN), ("", FG)]
        for k in range(1, len(cmd) + 1, type_step):
            frames.append([*base, (cmd[:k], FG)])
        frames.append([*base, (cmd, FG)])
        for k in range(2, len(out) + 1, reveal_step):
            frames.append([*base, *(("  " + t, FG) for t in out[:k])])
        terminal = [*base, *(("  " + t, FG) for t in out), ("", FG)]
        frames.append(terminal)
        if idx < len(USERS) - 1:
            frames.append(terminal)  # 段间停顿 1 帧

    frames += [frames[-1]] * 36  # 表格全部出现后静止 ≥3 s
    return frames


def main() -> None:
    fonts = load_fonts()
    frames = build_frames(fonts)
    total_s = len(frames) / FPS
    assert 120 <= len(frames) <= 144, f"帧数 {len(frames)} 不在 120-144"
    assert 10 <= total_s <= 12

    maxw = int(max(text_width(t, fonts) for f in frames for t, _ in f)) + PAD * 2
    maxh = max(len(f) for f in frames) * LH + PAD * 2
    print(f"canvas {maxw}x{maxh}, frames={len(frames)}, ~{total_s:.1f}s")

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
    print(f"written {OUT} ({OUT.stat().st_size / 1024:.0f} KB), frames={len(frames)}, ~{total_s:.1f}s")


if __name__ == "__main__":
    main()
