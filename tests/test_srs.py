from examdiag.diagnose import RootCause
from examdiag.srs import DayPlan, plan_week


def make_diagnosis(mastery_by_id: dict[str, float]):
    causes = [
        RootCause(
            concept_id=cid,
            name=cid,
            mastery=m,
            score=1 - m,
            wrong_count=5,
            min_distance=0,
            remedy_path=[cid],
            explains=[],
        )
        for cid, m in mastery_by_id.items()
    ]
    return type("D", (), {"root_causes": causes, "mastery": dict(mastery_by_id)})()


def test_day1_contains_all_root_causes_weakest_first():
    d = make_diagnosis({"weak": 0.05, "mid": 0.30, "strong": 0.45})
    plans = plan_week(d)
    assert [p.day for p in plans] == list(range(1, 8))
    assert all(isinstance(p, DayPlan) for p in plans)
    day1 = plans[0].concepts
    assert set(day1) == {"weak", "mid", "strong"}
    assert day1 == ["weak", "mid", "strong"]  # mastery 升序


def test_weaker_concept_repeats_more_often():
    d = make_diagnosis({"weak": 0.05, "strong": 0.45})
    plans = plan_week(d)
    count = {cid: sum(cid in p.concepts for p in plans) for cid in ("weak", "strong")}
    assert count["weak"] == 7  # interval 1 → 每天
    assert count["strong"] == 3  # interval 3 → 第 1/4/7 天
    assert count["weak"] > count["strong"]


def test_intervals_follow_inverse_mastery():
    d = make_diagnosis({"a": 0.45, "b": 0.20, "c": 0.02})
    plans = plan_week(d)
    days = {cid: [p.day for p in plans if cid in p.concepts] for cid in "abc"}
    assert days["a"] == [1, 4, 7]  # round(6*0.45)=3
    assert days["b"] == [1, 2, 3, 4, 5, 6, 7] or days["b"] == [1, 3, 5, 7]  # round(1.2)=1
    assert days["c"] == [1, 2, 3, 4, 5, 6, 7]


def test_no_concepts_beyond_root_causes_and_horizon_respected():
    d = make_diagnosis({"x": 0.10})
    plans = plan_week(d, horizon=7)
    every = {cid for p in plans for cid in p.concepts}
    assert every == {"x"}
    assert len(plans) == 7
    assert all(p.day <= 7 for p in plans)


def test_empty_diagnosis_gives_seven_empty_days():
    d = make_diagnosis({})
    plans = plan_week(d)
    assert [p.day for p in plans] == list(range(1, 8))
    assert all(p.concepts == [] for p in plans)


def test_to_dict_shape():
    d = make_diagnosis({"x": 0.1})
    payload = plan_week(d)[0].to_dict()
    assert payload == {"day": 1, "concepts": ["x"]}
