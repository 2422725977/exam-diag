# ruff: noqa: E501
"""软著说明书 PDF 构建（Wave 4 任务 4.2b）：docs/copyright/manual.md → manual.pdf。

支持的 markdown 子集：#/##/### 标题、段落（**加粗**、`行内码`）、- 列表、
N. 列表、| 表格 |、![截图](相对路径)、```代码块```。
中文字体 STHeiti（TTC 子字体 0），代码 Menlo，CJK 自动换行；
每页页眉（软件全称 + 版本 + 手册名）与页脚页码。页数用 pypdf 实读校验。

运行：python scripts/build_manual_pdf.py
"""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/copyright/manual.md"
OUT = ROOT / "docs/copyright/manual.pdf"
ASSETS = ROOT / "docs/copyright"

SOFTWARE = "exam-diag 考试错题根因诊断系统"
VERSION = "V0.5.0"

PAGE_W, PAGE_H = A4
M_L, M_R, M_T, M_B = 2.2 * cm, 2.2 * cm, 2.6 * cm, 2.2 * cm
CONTENT_W = PAGE_W - M_L - M_R


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("Heiti", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))
    pdfmetrics.registerFont(TTFont("MenloDoc", "/System/Library/Fonts/Menlo.ttc", subfontIndex=0))


def styles() -> dict[str, ParagraphStyle]:
    base = dict(fontName="Heiti", wordWrap="CJK", textColor=colors.HexColor("#111111"))
    return {
        "cover_title": ParagraphStyle("ct", fontSize=26, leading=44, alignment=TA_CENTER,
                                      spaceAfter=18, **base),
        "cover_sub": ParagraphStyle("cs", fontSize=14, leading=26, alignment=TA_CENTER,
                                    **base),
        "h2": ParagraphStyle("h2", fontSize=17, leading=26, spaceBefore=20, spaceAfter=12,
                             **base),
        "h3": ParagraphStyle("h3", fontSize=14, leading=22, spaceBefore=14, spaceAfter=9,
                             **base),
        "body": ParagraphStyle("body", fontSize=13, leading=24, spaceAfter=9,
                               firstLineIndent=0, **base),
        "li": ParagraphStyle("li", fontSize=13, leading=24, spaceAfter=5,
                             leftIndent=18, **base),
        "code": ParagraphStyle("code", fontName="MenloDoc", fontSize=9.5, leading=15,
                               backColor=colors.HexColor("#f5f6f8"),
                               borderPadding=6, leftIndent=6, rightIndent=6,
                               spaceBefore=6, spaceAfter=8),
        "cell": ParagraphStyle("cell", fontSize=11.5, leading=18, **base),
        "cellh": ParagraphStyle("cellh", fontSize=11.5, leading=18, **base),
        "caption": ParagraphStyle("cap", fontSize=10, leading=15, alignment=TA_CENTER,
                                  spaceBefore=2, spaceAfter=10, **base),
    }


def esc(text: str) -> str:
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="MenloDoc" size="11.5">\1</font>', text)
    return text


def make_table(rows: list[list[str]], st: dict) -> Table:
    data = []
    for i, row in enumerate(rows):
        style = st["cellh"] if i == 0 else st["cell"]
        data.append([Paragraph(esc(c), style) for c in row])
    ncol = max(len(r) for r in rows)
    widths = [CONTENT_W / ncol] * ncol
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fb")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    return t


def make_image(path: Path, st: dict) -> list:
    from PIL import Image as PILImage

    with PILImage.open(path) as im:
        w, h = im.size
    disp_w = CONTENT_W
    disp_h = disp_w * h / w
    max_h = PAGE_H - M_T - M_B - 2 * cm
    if disp_h > max_h:
        disp_h = max_h
        disp_w = disp_h * w / h
    return [
        Image(str(path), width=disp_w, height=disp_h),
        Paragraph(f"图：{path.name}", st["caption"]),
    ]


def parse(md: str, st: dict) -> list:
    flow = []
    lines = md.splitlines()
    i, n = 0, len(lines)
    first_h1 = True
    while i < n:
        line = lines[i]
        if line.strip() == "<!-- pagebreak -->":
            flow.append(PageBreak())
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            flow.append(Preformatted("\n".join(buf), st["code"]))
            continue
        if line.startswith("|"):
            rows = []
            while i < n and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            flow.append(make_table(rows, st))
            flow.append(Spacer(1, 8))
            continue
        if line.startswith("!["):
            alt, path = re.match(r"!\[(.*?)\]\((.*?)\)", line).groups()
            flow.extend(make_image(ASSETS / path, st))
            flow.append(Paragraph(esc(alt), st["caption"]))
            i += 1
            continue
        if line.startswith("### "):
            flow.append(Paragraph(esc(line[4:]), st["h3"]))
            i += 1
            continue
        if line.startswith("## "):
            flow.append(Paragraph(esc(line[3:]), st["h2"]))
            i += 1
            continue
        if line.startswith("# "):
            text = esc(line[2:])
            if first_h1:
                flow.append(Paragraph(text, st["cover_title"]))
                first_h1 = False
            else:
                flow.append(Paragraph(esc(line[2:]), st["h2"]))
            i += 1
            continue
        if line.startswith("- "):
            flow.append(Paragraph(esc(line[2:]), st["li"], bulletText="•"))
            i += 1
            continue
        m = re.match(r"^(\d+)\. (.*)$", line)
        if m:
            flow.append(Paragraph(esc(m.group(2)), st["li"], bulletText=f"{m.group(1)}."))
            i += 1
            continue
        flow.append(Paragraph(esc(line), st["body"]))
        i += 1
    return flow


def decorate(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Heiti", 9)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(M_L, PAGE_H - 1.5 * cm, f"{SOFTWARE} {VERSION}  用户操作手册")
    canvas.drawRightString(PAGE_W - M_R, PAGE_H - 1.5 * cm, "软著申请材料")
    canvas.setStrokeColor(colors.HexColor("#aaaaaa"))
    canvas.line(M_L, PAGE_H - 1.7 * cm, PAGE_W - M_R, PAGE_H - 1.7 * cm)
    canvas.drawCentredString(PAGE_W / 2, 1.3 * cm, f"- {canvas.getPageNumber()} -")
    canvas.restoreState()


def main() -> None:
    register_fonts()
    st = styles()
    md = SRC.read_text(encoding="utf-8")
    flow = parse(md, st)

    doc = BaseDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=M_L, rightMargin=M_R, topMargin=M_T, bottomMargin=M_B,
        title=f"{SOFTWARE} {VERSION} 用户手册", author="Xin Xia",
    )
    frame = Frame(M_L, M_B, CONTENT_W, PAGE_H - M_T - M_B, id="main")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=decorate)])
    doc.build(flow)

    real = len(PdfReader(OUT).pages)
    print(f"written {OUT}")
    print(f"PDF pages (pypdf): {real}")


if __name__ == "__main__":
    main()
