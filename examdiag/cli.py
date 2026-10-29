"""Command-line interface.

    examdiag diagnose --attempts data/demo_attempts.jsonl --concepts data/concepts/
        [--questions data/questions/] [--user ID] [--top N] [--plan] [--json]
    examdiag report   --attempts data/demo_attempts.jsonl --concepts data/concepts/
        [--user ID] [--format md|csv|xlsx|html] [--out PATH] [--json]

--concepts / --questions 都接受单文件或目录（目录时合并全部 *.yaml / *.jsonl）。
--questions 缺省时自动取 --concepts 的同级 questions 目录。
配置缺省值来自 ~/.examdiag.toml（或 ./.examdiag.toml），见 examdiag/config.py。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from . import __version__
from .config import load_config
from .diagnose import Diagnosis, diagnose
from .schema import ConceptGraph, load_attempts, load_concepts, load_questions
from .srs import plan_week, sm2_plan

SOFTWARE = "exam-diag 考试错题根因诊断系统"


def _expand_concepts(path: Path) -> ConceptGraph:
    files = sorted(path.glob("*.yaml")) if path.is_dir() else [path]
    if not files:
        raise FileNotFoundError(f"no concepts yaml under {path}")
    merged: dict[str, object] = {}
    for f in files:
        merged.update(load_concepts(f).concepts)
    return ConceptGraph(concepts=merged)  # type: ignore[arg-type]


def _expand_questions(path: Path | None, concepts_path: Path) -> list:
    if path is None:
        parent = concepts_path.parent if concepts_path.is_file() else concepts_path
        path = parent.parent / "questions"
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    if not files:
        raise FileNotFoundError(f"no questions jsonl under {path}")
    out = []
    for f in files:
        out.extend(load_questions(f))
    return out


def _render(diag: Diagnosis, concepts: ConceptGraph, console: Console,
            show_plan: bool, use_sm2: bool, max_per_day: int) -> None:
    if not diag.root_causes:
        console.print("[green]没有发现需要归因的错误模式（无错题或样本不足）。[/green]")
    table = Table(title="根因诊断报告", title_style="bold", header_style="bold cyan")
    table.add_column("#", justify="right")
    table.add_column("根因概念")
    table.add_column("掌握度", justify="right")
    table.add_column("涉及错题", justify="right")
    table.add_column("补习路径（按序补）")
    for i, r in enumerate(diag.root_causes, 1):
        mastery_color = "red" if r.mastery < 0.3 else "yellow"
        path_names = " → ".join(
            f"{concepts.concepts[cid].name}({cid})" for cid in r.remedy_path
        )
        table.add_row(
            str(i),
            f"[bold]{r.name}[/bold] [dim]{r.concept_id}[/dim]",
            f"[{mastery_color}]{r.mastery:.2f}[/{mastery_color}]",
            str(r.wrong_count),
            path_names,
        )
    console.print(table)
    if diag.insufficient_data:
        ids = ", ".join(diag.insufficient_data)
        console.print(f"[dim]insufficient_data（作答 < 3 次，不下结论）: {ids}[/dim]")
    if show_plan and diag.root_causes:
        plan_table = Table(title="未来 7 天复习计划", header_style="bold magenta")
        plan_table.add_column("天", justify="right")
        plan_table.add_column("复习概念（最弱优先）")
        names = {cid: f"{c.name}({cid})" for cid, c in concepts.concepts.items()}
        plans = sm2_plan(diag, max_per_day=max_per_day) if use_sm2 else plan_week(diag)
        for p in plans:
            plan_table.add_row(
                f"Day {p.day}",
                ", ".join(names[cid] for cid in p.concepts) or "[dim]休息[/dim]",
            )
        console.print(plan_table)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--attempts", required=True, help="作答记录 jsonl（单文件）")
    parser.add_argument("--concepts", required=True, help="概念图谱 yaml 文件或目录")
    parser.add_argument("--questions", default=None, help="题库 jsonl 文件或目录（缺省自动发现）")
    parser.add_argument("--user", default=None, help="只诊断该用户（缺省合并全部）")
    parser.add_argument("--config", default=None, help="配置 toml 路径（缺省自动发现）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="examdiag",
        description="Find the root-cause concept behind every wrong answer.",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"{SOFTWARE} V{__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("diagnose", help="诊断错题的根因概念")
    _add_common(d)
    d.add_argument("--top", type=int, default=None, help="最多输出几个根因（缺省取配置）")
    d.add_argument("--plan", action="store_true", help="附带输出 7 天复习计划")
    d.add_argument("--sm2", action="store_true", help="复习计划用 SM-2 调度（默认轻量版）")
    d.add_argument("--json", action="store_true", help="以 JSON 输出（供脚本消费）")

    r = sub.add_parser("report", help="导出诊断报告（md/csv/xlsx/html）")
    _add_common(r)
    r.add_argument("--format", default="md", choices=["md", "csv", "xlsx", "html"])
    r.add_argument("--out", default=None, help="输出路径（缺省 <配置 output_dir>/report.<fmt>）")
    r.add_argument("--json", action="store_true", help="以 JSON 输出落盘信息")

    args = parser.parse_args(argv)
    console = Console()

    try:
        cfg = load_config(args.config)
        concepts = _expand_concepts(Path(args.concepts))
        questions = _expand_questions(
            Path(args.questions) if args.questions else None, Path(args.concepts)
        )
        attempts = load_attempts(args.attempts)
        top_n = (
            args.top if args.command == "diagnose" and args.top is not None
            else cfg.diagnose.top_n
        )
        diag = diagnose(
            attempts, questions, concepts, user_id=args.user,
            top_n=top_n, mastery_threshold=cfg.diagnose.mastery_threshold,
        )
    except (FileNotFoundError, KeyError, ValueError) as e:
        console.print(f"[red]error:[/red] {e}")
        return 1

    if args.command == "diagnose":
        if args.json:
            payload = diag.to_dict()
            if args.plan:
                plans = (sm2_plan(diag, max_per_day=cfg.srs.max_per_day)
                         if args.sm2 else plan_week(diag, span=cfg.srs.span))
                payload["plan"] = [p.to_dict() for p in plans]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _render(diag, concepts, console, show_plan=args.plan,
                    use_sm2=args.sm2, max_per_day=cfg.srs.max_per_day)
        return 0

    # ---- report 子命令 ----
    from .report import export_mapping_csv, export_markdown, export_xlsx, write_html

    out = Path(args.out) if args.out else cfg.report.output_dir / f"report.{args.format}"
    cmd = (f"examdiag report --attempts {args.attempts} --concepts {args.concepts} "
           f"--format {args.format}")
    try:
        if args.format == "md":
            path = export_markdown(diag, concepts, out)
        elif args.format == "csv":
            path = export_mapping_csv(diag, concepts, attempts, questions, out,
                                      user_id=args.user)
        elif args.format == "xlsx":
            path = export_xlsx(diag, concepts, attempts, questions, out,
                               user_id=args.user)
        else:
            path = write_html(diag, concepts, attempts, questions, out, cmd_line=cmd)
    except ImportError as e:
        console.print(f"[red]error:[/red] {e}（xlsx 需要 pip install 'exam-diag[report]'）")
        return 1
    if args.json:
        print(json.dumps({"written": str(path), "size": path.stat().st_size},
                         ensure_ascii=False))
    else:
        console.print(f"[green]written[/green] {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
