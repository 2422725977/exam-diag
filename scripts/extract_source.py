# ruff: noqa: E501
"""软著申请材料 4.1：源程序 PDF（docs/copyright/source-60p.pdf）。

内容：仓库全部真实 Python 源码（examdiag/ 核心包 1,036 行 + tests/ 897 行 +
scripts/ 1,318 行，共约 3,251 行；examdiag/ 单独不足 30 页，故按"全程序"收录，
构成在页眉下方与报告中如实注明）。
排版：每页 50 行、行号、页眉含软件全称 + 版本号 + 页码；
     总页数 > 60 时按软著惯例取前 30 页 + 后 30 页。
渲染：PIL 逐页绘制（Menlo + STHeiti 逐字符回退），PIL 多页合成 A4 PDF（150dpi）。
页数用 pypdf 实读校验。

运行：python scripts/extract_source.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/copyright/source-60p.pdf"

SOFTWARE = "exam-diag 考试错题根因诊断系统"
VERSION = "V0.6.0"
LINES_PER_PAGE = 50
DPI = 150
PAGE_W, PAGE_H = 1240, 1754  # A4 @150dpi
MARGIN_X, MARGIN_Y = 50, 56
ROW_H = 30
SIZE = 15  # Menlo
SIZE_CJK = 19  # STHeiti（≈2 格宽）

FONT_LATIN = "/System/Library/Fonts/Menlo.ttc"
FONT_CJK = "/System/Library/Fonts/STHeiti Medium.ttc"

FILE_ORDER = [
    "examdiag/__init__.py", "examdiag/schema.py", "examdiag/bkt.py",
    "examdiag/graph.py", "examdiag/diagnose.py", "examdiag/srs.py",
    "examdiag/report.py", "examdiag/config.py",
    "examdiag/eval.py", "examdiag/cli.py",
]


def load_fonts():
    return (
        ImageFont.truetype(FONT_LATIN, SIZE),
        ImageFont.truetype(FONT_CJK, SIZE_CJK),
    )


def draw_mixed(draw, xy, text, fonts, fill):
    """逐字符混排（CJK 用 STHeiti），返回结束 x。"""
    fl, fc = fonts
    x, y = xy
    for ch in text:
        f = fc if ord(ch) >= 0x2E80 else fl
        draw.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch)
    return x


def collect_lines() -> tuple[list[str], dict[str, int]]:
    """按逻辑顺序收集全部源码行（文件头注释行计入，真实可审计）。"""
    lines: list[str] = []
    per_file: dict[str, int] = {}
    ordered = FILE_ORDER[:]
    ordered += sorted(p.as_posix() for p in Path(ROOT, "tests").glob("*.py"))
    ordered += sorted(p.as_posix() for p in Path(ROOT, "scripts").glob("*.py"))
    for i, rel in enumerate(ordered):
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").rstrip("\n")
        body = text.splitlines()
        header = f"# ============ 文件: {rel}  ({len(body)} 行) ============"
        chunk = [header, *body]
        if i < len(ordered) - 1:  # 末文件不加尾部分隔：册子以程序自然结束收尾
            chunk.append("")
        per_file[rel] = len(body)
        lines.extend(chunk)
    return lines, per_file


def paginate(lines: list[str]) -> list[list[str]]:
    pages = [lines[i : i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)]
    if len(pages) > 60:  # 软著惯例：全程序超 60 页取前 30 + 后 30
        pages = pages[:30] + pages[-30:]
    return pages


def render_pages(pages: list[list[str]], fonts) -> list[Image.Image]:
    imgs = []
    total = len(pages)
    for idx, page_lines in enumerate(pages, 1):
        img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        d = ImageDraw.Draw(img)
        # 页眉：软件全称 + 版本号 + 页码
        draw_mixed(d, (MARGIN_X, 20), f"{SOFTWARE}  {VERSION}", fonts, "black")
        page_tag = f"源程序  第 {idx} 页 / 共 {total} 页"
        draw_mixed(d, (PAGE_W - MARGIN_X - 330, 20), page_tag, fonts, "black")
        d.line([(MARGIN_X, 52), (PAGE_W - MARGIN_X, 52)], fill="black", width=2)
        if idx == 1:
            note = "（收录范围：examdiag/ 核心包 + tests/ 测试 + scripts/ 工具脚本，全部真实源码）"
            draw_mixed(d, (MARGIN_X, 56), note, fonts, (90, 90, 90))
        y = 92 if idx == 1 else 72
        for i, line in enumerate(page_lines, 1):
            no = f"{(idx - 1) * LINES_PER_PAGE + i:>4}  "
            d.text((MARGIN_X, y), no, font=fonts[0], fill=(120, 120, 120))
            draw_mixed(d, (MARGIN_X + 58, y), line[:150], fonts, "black")
            y += ROW_H
        imgs.append(img)
    return imgs


def main() -> None:
    fonts = load_fonts()
    lines, per_file = collect_lines()
    total_lines = len(lines)
    pages = paginate(lines)
    imgs = render_pages(pages, fonts)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].save(
        OUT, save_all=True, append_images=imgs[1:], resolution=DPI,
        title=f"{SOFTWARE} {VERSION} 源程序",
    )
    real_pages = len(PdfReader(OUT).pages)
    print(f"written {OUT}")
    print(f"source files: {len(per_file)}, listing lines: {total_lines:,}")
    print(f"examdiag/ core: {sum(v for k, v in per_file.items() if k.startswith('examdiag/')):,} lines")
    print(f"pages rendered: {len(pages)} (per-page {LINES_PER_PAGE} lines), PDF pages (pypdf): {real_pages}")
    # 鉴别材料规则：最后一页必须以程序自然结束收尾（最后一行 = 末文件末行）
    last = pages[-1][-1].strip()
    print(f"page {real_pages} ends with: {last[:70]!r}")


if __name__ == "__main__":
    sys.exit(main())
