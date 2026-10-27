from datetime import datetime, timedelta

import pytest

from examdiag.diagnose import (
    MASTERY_THRESHOLD,
    MIN_ATTEMPTS,
    Diagnosis,
    collect_sequences,
    diagnose,
    estimate_mastery,
    score,
)
from examdiag.schema import Attempt, Concept, ConceptGraph, Question

T0 = datetime(2026, 10, 20, 9, 0, 0)


def build_world():
    """链：a -> b -> c；旁支：d（无前置）、e（前置 d）。

    a=栈(会), b=遍历(不会), c=旋转(不会) 的最小复刻。
    """
    concepts = ConceptGraph.from_list([
        Concept(id="s.a", name="A基础", subject="408", difficulty=2, prereqs=[]),
        Concept(id="s.b", name="B中级", subject="408", difficulty=3, prereqs=["s.a"]),
        Concept(id="s.c", name="C高级", subject="408", difficulty=5, prereqs=["s.b"]),
        Concept(id="s.d", name="D独立", subject="408", difficulty=3, prereqs=[]),
        Concept(id="s.e", name="E依赖D", subject="408", difficulty=4, prereqs=["s.d"]),
    ])
    questions = []
    pairs = [("q-a", "s.a"), ("q-b", "s.b"), ("q-c", "s.c"), ("q-d", "s.d"), ("q-e", "s.e")]
    for prefix, cid in pairs:
        questions += [
            Question(id=f"{prefix}{i}", subject="408", stem="s", answer="A",
                     concepts=[cid], source="self-built")
            for i in range(4)
        ]
    return concepts, questions


def attempts_for(pattern: dict[str, list[int]]):
    """pattern: 问题 id 前缀 -> 作答序列（0/1），时间依次递增。"""
    out = []
    t = T0
    for prefix, answers in pattern.items():
        for i, ok in enumerate(answers):
            out.append(
                Attempt(user_id="u1", question_id=f"{prefix}{i}", correct=bool(ok), ts=t)
            )
            t += timedelta(minutes=10)
    return out


# ---------- collect_sequences / estimate_mastery ----------


def test_collect_sequences_sorts_by_ts_and_fans_out_concepts():
    concepts, questions = build_world()
    qmulti = Question(id="q-multi", subject="408", stem="s", answer="A",
                      concepts=["s.a", "s.b"], source="self-built")
    attempts = [
        Attempt(user_id="u1", question_id="q-multi", correct=True, ts=T0 + timedelta(minutes=5)),
        Attempt(user_id="u1", question_id="q-a0", correct=False, ts=T0),
    ]
    seqs = collect_sequences(attempts, [*questions, qmulti])
    assert seqs["s.a"] == [0, 1]  # 按 ts 排序后 a 先错后对
    assert seqs["s.b"] == [1]
    assert "s.c" not in seqs


def test_collect_sequences_unknown_question_raises():
    _, questions = build_world()
    ghost = Attempt(user_id="u1", question_id="ghost", correct=True, ts=T0)
    with pytest.raises(KeyError):
        collect_sequences([ghost], questions)


def test_estimate_mastery_marks_insufficient_below_min_attempts():
    seqs = {"s.a": [1, 1, 1], "s.b": [0, 0]}
    mastery, insufficient = estimate_mastery(seqs)
    assert "s.a" in mastery
    assert insufficient == ["s.b"]
    assert len(seqs) == 2 and MIN_ATTEMPTS == 3


def test_collect_sequences_user_filter():
    concepts, questions = build_world()
    attempts = [
        Attempt(user_id="u1", question_id="q-a0", correct=True, ts=T0),
        Attempt(user_id="u2", question_id="q-a1", correct=False, ts=T0),
    ]
    seqs = collect_sequences(attempts, questions, user_id="u2")
    assert seqs == {"s.a": [0]}
    with pytest.raises(KeyError):
        collect_sequences(attempts, questions, user_id="nobody")


# ---------- score 公式（SPEC 5.3 字面实现） ----------


def test_score_matches_spec_formula():
    g_concepts, _ = build_world()
    from examdiag.graph import build

    g = build(g_concepts)
    # a(0.9) -> b(0.2) -> c(0.5)
    m = {"s.a": 0.9, "s.b": 0.2, "s.c": 0.5}
    assert score(g, "s.a", m) == pytest.approx(1 - 0.9)  # 无有数据前置
    assert score(g, "s.b", m) == pytest.approx(0.8 * 0.1)  # d=1
    assert score(g, "s.c", m) == pytest.approx(0.5 * 0.1 ** (1 / 2) * 0.8)  # b d=1, a d=2


def test_score_skips_insufficient_ancestors():
    g_concepts, _ = build_world()
    from examdiag.graph import build

    g = build(g_concepts)
    # s.a 无数据 → b 的乘积只剩它自己
    assert score(g, "s.b", {"s.b": 0.3}) == pytest.approx(0.7)


# ---------- diagnose 主流程 ----------


def test_symptom_filter_picks_upstream_root_cause():
    """a 掌握、b/c 连错 → 根因是 b（最上游未掌握），c 是症状被过滤。"""
    concepts, questions = build_world()
    attempts = attempts_for({
        "q-a": [1, 1, 1, 1],
        "q-b": [0, 0, 1, 0],
        "q-c": [0, 0, 0, 0],
        "q-d": [1, 1, 1, 1],
    })
    d = diagnose(attempts, questions, concepts)
    assert d.root_causes[0].concept_id == "s.b"
    ids = [r.concept_id for r in d.root_causes]
    assert "s.c" not in ids  # c 的前置 b 未掌握 → 症状
    assert d.root_causes[0].explains == ["s.c"]
    assert d.root_causes[0].remedy_path == ["s.b", "s.c"]


def test_mastered_ancestor_keeps_downstream_as_root():
    """a 掌握、b 连错且 a 已会 → b 自己就是根因。"""
    concepts, questions = build_world()
    attempts = attempts_for({
        "q-a": [1, 1, 1, 1],
        "q-b": [0, 0, 0, 0],
        "q-c": [0, 0, 0, 0],
        "q-d": [1, 1, 1, 1],
    })
    d = diagnose(attempts, questions, concepts)
    assert d.root_causes[0].concept_id == "s.b"
    assert d.mastery["s.a"] > MASTERY_THRESHOLD


def test_insufficient_data_concept_not_root_but_propagates_upstream():
    """c 只有 2 次作答 → insufficient；b 的失败仍把根因指到 b。"""
    concepts, questions = build_world()
    attempts = [
        Attempt(user_id="u1", question_id="q-a0", correct=True, ts=T0),
        Attempt(user_id="u1", question_id="q-a1", correct=True, ts=T0 + timedelta(minutes=1)),
        Attempt(user_id="u1", question_id="q-a2", correct=True, ts=T0 + timedelta(minutes=2)),
        Attempt(user_id="u1", question_id="q-b0", correct=False, ts=T0 + timedelta(minutes=3)),
        Attempt(user_id="u1", question_id="q-b1", correct=False, ts=T0 + timedelta(minutes=4)),
        Attempt(user_id="u1", question_id="q-b2", correct=False, ts=T0 + timedelta(minutes=5)),
        Attempt(user_id="u1", question_id="q-c0", correct=False, ts=T0 + timedelta(minutes=6)),
        Attempt(user_id="u1", question_id="q-c1", correct=False, ts=T0 + timedelta(minutes=7)),
    ]
    d = diagnose(attempts, questions, concepts)
    assert "s.c" in d.insufficient_data
    assert [r.concept_id for r in d.root_causes] == ["s.b"]


def test_no_wrong_attempts_gives_empty_diagnosis():
    concepts, questions = build_world()
    attempts = attempts_for({"q-a": [1, 1, 1], "q-d": [1, 1, 1]})
    d = diagnose(attempts, questions, concepts)
    assert d.root_causes == []
    assert d.insufficient_data == ["s.a", "s.d"] or d.insufficient_data == []


def test_min_distance_zero_when_root_itself_wrong():
    concepts, questions = build_world()
    attempts = attempts_for({
        "q-a": [1, 1, 1, 1],
        "q-b": [0, 0, 0, 0],
        "q-c": [0, 0, 0, 0],
    })
    d = diagnose(attempts, questions, concepts)
    r = d.root_causes[0]
    assert r.min_distance == 0
    assert r.wrong_count >= 4  # 至少包含自己概念的错题


def test_diagnosis_to_dict_roundtrip():
    concepts, questions = build_world()
    attempts = attempts_for({"q-a": [1, 1, 1, 1], "q-b": [0, 0, 0, 0]})
    d = diagnose(attempts, questions, concepts)
    assert isinstance(d, Diagnosis)
    payload = d.to_dict()
    assert payload["root_causes"][0]["concept_id"] == "s.b"
    # 全错序列在退化兜底（默认参数）下 mastery 必须很低
    assert payload["root_causes"][0]["mastery"] < 0.3
    assert payload["root_causes"][0]["mastery"] < MASTERY_THRESHOLD
