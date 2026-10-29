import json
from datetime import datetime, timedelta

import pytest

from examdiag.cli import _expand_concepts, _expand_questions, main
from examdiag.schema import Attempt, Question

T0 = datetime(2026, 10, 20, 9, 0, 0)


@pytest.fixture
def world(tmp_path):
    """data 布局复刻：concepts/ 两科 yaml + questions/ 两科 jsonl + attempts.jsonl。"""
    cdir = tmp_path / "concepts"
    qdir = tmp_path / "questions"
    cdir.mkdir()
    qdir.mkdir()

    (cdir / "s1.yaml").write_text(
        "- {id: s.a, name: A基础, subject: 408, difficulty: 2, prereqs: []}\n"
        "- {id: s.b, name: B中级, subject: 408, difficulty: 3, prereqs: [s.a]}\n",
        encoding="utf-8",
    )
    (cdir / "s2.yaml").write_text(
        "- {id: s.d, name: D独立, subject: 408, difficulty: 3, prereqs: []}\n",
        encoding="utf-8",
    )
    questions = [
        *[Question(id=f"q-a{i}", subject="408", stem="s", answer="A",
                   concepts=["s.a"], source="self-built") for i in range(4)],
        *[Question(id=f"q-b{i}", subject="408", stem="s", answer="A",
                   concepts=["s.b"], source="self-built") for i in range(4)],
        *[Question(id=f"q-d{i}", subject="408", stem="s", answer="A",
                   concepts=["s.d"], source="self-built") for i in range(4)],
    ]
    with open(qdir / "s1.jsonl", "w", encoding="utf-8") as f:
        for q in questions[:8]:
            f.write(q.model_dump_json() + "\n")
    with open(qdir / "s2.jsonl", "w", encoding="utf-8") as f:
        for q in questions[8:]:
            f.write(q.model_dump_json() + "\n")

    attempts, t = [], T0
    for qid, ok in [("q-a0", 1), ("q-a1", 1), ("q-a2", 1), ("q-a3", 1),
                    ("q-b0", 0), ("q-b1", 0), ("q-b2", 1), ("q-b3", 0),
                    ("q-d0", 0)]:
        attempts.append(Attempt(user_id="u1", question_id=qid, correct=bool(ok), ts=t))
        t += timedelta(minutes=5)
    with open(tmp_path / "attempts.jsonl", "w", encoding="utf-8") as f:
        for a in attempts:
            f.write(a.model_dump_json() + "\n")
    return tmp_path


def test_expand_concepts_merges_directory(world):
    g = _expand_concepts(world / "concepts")
    assert set(g.concepts) == {"s.a", "s.b", "s.d"}


def test_expand_questions_directory_and_default_discovery(world):
    qs = _expand_questions(world / "questions", world / "concepts")
    assert len(qs) == 12
    # 缺省 = concepts 同级的 questions 目录
    assert len(_expand_questions(None, world / "concepts")) == 12


def test_cli_json_first_root_cause(world, capsys):
    rc = main([
        "diagnose",
        "--attempts", str(world / "attempts.jsonl"),
        "--concepts", str(world / "concepts"),
        "--json",
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["root_causes"][0]["concept_id"] == "s.b"
    assert "s.d" in payload["insufficient_data"]  # 只答 1 次


def test_cli_table_render(world, capsys):
    rc = main([
        "diagnose",
        "--attempts", str(world / "attempts.jsonl"),
        "--concepts", str(world / "concepts"),
        "--plan",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "根因诊断报告" in out
    assert "B中级" in out
    assert "未来 7 天复习计划" in out


def test_cli_missing_file_returns_error(world, capsys):
    rc = main([
        "diagnose",
        "--attempts", str(world / "nope.jsonl"),
        "--concepts", str(world / "concepts"),
    ])
    assert rc == 1
    assert "error" in capsys.readouterr().out


def test_cli_user_filter_and_top(world, capsys):
    rc = main([
        "diagnose",
        "--attempts", str(world / "attempts.jsonl"),
        "--concepts", str(world / "concepts"),
        "--user", "nobody",
        "--json",
    ])
    assert rc == 1  # 该用户无作答 → 报错退出


def test_version_closed_loop(capsys):
    """--version 输出全称+版本（名称/版本四处一致闭环的运行侧证据）。"""
    from examdiag import __version__
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "考试错题根因诊断系统" in out
    assert f"V{__version__}" in out


def test_report_subcommand_md(world, tmp_path):
    rc = main([
        "report",
        "--attempts", str(world / "attempts.jsonl"),
        "--concepts", str(world / "concepts"),
        "--format", "md",
        "--out", str(tmp_path / "r.md"),
    ])
    assert rc == 0
    text = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "根因" in text and "s.b" in text


def test_report_subcommand_csv(world, tmp_path):
    out = tmp_path / "r.csv"
    rc = main([
        "report",
        "--attempts", str(world / "attempts.jsonl"),
        "--concepts", str(world / "concepts"),
        "--format", "csv",
        "--out", str(out),
    ])
    assert rc == 0
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")


def test_config_affects_top_n(world, tmp_path, capsys):
    cfg = tmp_path / "c.toml"
    cfg.write_text("[diagnose]\ntop_n = 1\n", encoding="utf-8")
    rc = main([
        "diagnose",
        "--attempts", str(world / "attempts.jsonl"),
        "--concepts", str(world / "concepts"),
        "--config", str(cfg),
        "--json",
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["root_causes"]) == 1  # top_n 来自配置
