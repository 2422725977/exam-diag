import json
from datetime import datetime

import pytest
import yaml
from pydantic import ValidationError

from examdiag.schema import (
    Attempt,
    Concept,
    ConceptGraph,
    Question,
    load_attempts,
    load_concepts,
    load_questions,
)


def concept(cid="ds.tree.bst", prereqs=None, subject="408", difficulty=3.0, name="二叉搜索树"):
    return Concept(id=cid, name=name, subject=subject, difficulty=difficulty, prereqs=prereqs or [])


def chain(ids):
    """ids 依序成链：ids[i+1] 的前置是 ids[i]。"""
    return [concept(cid=cid, prereqs=[ids[i - 1]] if i else []) for i, cid in enumerate(ids)]


# ---------- Concept ----------


def test_concept_defaults_and_fields():
    c = concept()
    assert c.prereqs == []
    assert c.subject == "408"
    assert c.name == "二叉搜索树"


def test_concept_coerces_yaml_int_subject():
    assert Concept(id="ds.a.b", name="x", subject=408, difficulty=3).subject == "408"


@pytest.mark.parametrize("bad", [0.9, 5.1, -1, "high"])
def test_concept_rejects_bad_difficulty(bad):
    with pytest.raises(ValidationError):
        concept(difficulty=bad)


@pytest.mark.parametrize("bad", ["tree", "DS.tree", "ds.tree!", "", "a.b."])
def test_concept_rejects_bad_id(bad):
    with pytest.raises(ValidationError):
        concept(cid=bad)


def test_concept_accepts_valid_hierarchical_ids():
    for cid in ["ds.tree.bst", "math.calc.limit", "eng.vocab.tense", "pol.marx.mat1"]:
        assert concept(cid=cid).id == cid


# ---------- Question ----------


def test_question_requires_at_least_one_concept():
    with pytest.raises(ValidationError):
        Question(id="q1", subject="408", stem="题干", answer="A", concepts=[], source="self-built")


def test_question_ok():
    q = Question(
        id="q408-0001", subject="408", stem="中序遍历二叉搜索树得到什么序列？", answer="升序序列",
        concepts=["ds.tree.bst"], source="self-built",
    )
    assert q.concepts == ["ds.tree.bst"]


# ---------- Attempt ----------


def test_attempt_parses_iso_timestamp():
    a = Attempt(user_id="u1", question_id="q1", correct=True, ts="2026-10-28T10:00:00")
    assert isinstance(a.ts, datetime)


def test_attempt_rejects_missing_user():
    with pytest.raises(ValidationError):
        Attempt(user_id="", question_id="q1", correct=False, ts="2026-10-28T10:00:00")


# ---------- ConceptGraph ----------


def test_graph_rejects_unknown_prereq():
    with pytest.raises(ValidationError, match="ghost"):
        ConceptGraph.from_list([concept(cid="ds.a.b"), concept(cid="ds.c.d", prereqs=["ghost"])])


def test_graph_detects_cycle_and_reports_path():
    items = [
        concept(cid="ds.a.a", prereqs=["ds.c.c"]),
        concept(cid="ds.b.b", prereqs=["ds.a.a"]),
        concept(cid="ds.c.c", prereqs=["ds.b.b"]),
    ]
    with pytest.raises(ValidationError, match="cycle") as exc:
        ConceptGraph.from_list(items)
    msg = str(exc.value)
    for cid in ("ds.a.a", "ds.b.b", "ds.c.c"):
        assert cid in msg


def test_graph_chain_is_acyclic_with_single_root():
    g = ConceptGraph.from_list(chain(["ds.a.a", "ds.b.b", "ds.c.c"]))
    assert g.roots() == ["ds.a.a"]
    assert g.topo_order() == ["ds.a.a", "ds.b.b", "ds.c.c"]
    assert g.ancestors("ds.c.c") == {"ds.a.a", "ds.b.b"}


def test_graph_self_loop_is_a_cycle():
    with pytest.raises(ValidationError):
        ConceptGraph.from_list([concept(cid="ds.a.a", prereqs=["ds.a.a"])])


# ---------- 文件加载 ----------


def test_load_concepts_yaml(tmp_path):
    payload = {
        "subject": "408",
        "concepts": [
            {"id": "ds.a.a", "name": "栈", "subject": "408", "difficulty": 2, "prereqs": []},
            {"id": "ds.b.b", "name": "递归", "subject": "408", "difficulty": 3,
             "prereqs": ["ds.a.a"]},
        ],
    }
    p = tmp_path / "408.yaml"
    p.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    g = load_concepts(p)
    assert len(g.concepts) == 2
    assert g.concepts["ds.b.b"].prereqs == ["ds.a.a"]


def test_load_questions_jsonl(tmp_path):
    lines = [
        json.dumps({"id": "q1", "subject": "408", "stem": "s", "answer": "a",
                    "concepts": ["ds.a.a"], "source": "self-built"}, ensure_ascii=False),
        "",
        json.dumps({"id": "q2", "subject": "408", "stem": "s2", "answer": "b",
                    "concepts": ["ds.a.a"], "source": "self-built"}, ensure_ascii=False),
    ]
    p = tmp_path / "408.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    qs = load_questions(p)
    assert [q.id for q in qs] == ["q1", "q2"]


def test_load_attempts_jsonl(tmp_path):
    rows = [
        {"user_id": "u1", "question_id": "q1", "correct": True, "ts": "2026-10-28T09:00:00"},
        {"user_id": "u1", "question_id": "q2", "correct": False, "ts": "2026-10-28T09:05:00"},
    ]
    p = tmp_path / "attempts.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    attempts = load_attempts(p)
    assert len(attempts) == 2
    assert attempts[1].correct is False
