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


# ---------- SM-2 变体 ----------

from examdiag.srs import (  # noqa: E402
    EF_MAX,
    EF_MIN,
    SM2Item,
    ef_from_mastery,
    sm2_plan,
    sm2_review,
)


def test_ef_mapping_monotonic_and_bounded():
    assert ef_from_mastery(0.0) == EF_MIN
    assert ef_from_mastery(1.0) == EF_MAX
    assert EF_MIN < ef_from_mastery(0.3) < ef_from_mastery(0.7) < EF_MAX
    assert ef_from_mastery(1.5) == EF_MAX  # 越界钳制


def test_sm2_review_success_grows_interval():
    it = SM2Item("c", easiness=2.0)  # 低于上限，便于观察 EF 增长
    it2 = sm2_review(it, 5)
    assert (it2.reps, it2.interval) == (1, 1)  # 种子 1
    it3 = sm2_review(it2, 5)
    assert it3.interval == 3  # 种子 3
    it4 = sm2_review(it3, 5)
    assert it4.interval == 7  # 种子 7
    it5 = sm2_review(it4, 5)
    assert it5.interval == round(7 * it5.easiness)  # 之后按 EF 增长
    assert it5.easiness > it4.easiness  # q=5 → EF 上升


def test_sm2_review_failure_resets_and_lowers_ef():
    it = SM2Item("c", easiness=2.5, interval=7, reps=3)
    out = sm2_review(it, 2)
    assert out.reps == 0 and out.interval == 1
    assert out.easiness < it.easiness  # q=2 → EF 下降
    assert out.easiness >= EF_MIN  # 不会击穿下限


def test_sm2_review_ef_clamped_both_sides():
    lo = SM2Item("c", easiness=EF_MIN)
    assert sm2_review(lo, 0).easiness == EF_MIN
    hi = SM2Item("c", easiness=EF_MAX)
    assert sm2_review(hi, 5).easiness == EF_MAX


def test_sm2_plan_day1_all_roots_and_cap():
    d = make_diagnosis({f"c{i}": 0.1 + i * 0.01 for i in range(25)})
    plans = sm2_plan(d, horizon=7, max_per_day=10)
    assert len(plans) == 7
    assert all(len(p.concepts) <= 10 for p in plans)  # 每日队列上限
    assert len(plans[0].concepts) == 10  # 首日饱和
    assert plans[0].concepts == sorted(plans[0].concepts, key=lambda c: d.mastery[c])
    # 全部 25 个根因最终都会被排入（失败/顺延不断重排）
    served = {c for p in plans for c in p.concepts}
    assert served == set(d.mastery)


def test_sm2_plan_uses_grades_for_simulation():
    d = make_diagnosis({"a": 0.4})
    plans = sm2_plan(d, horizon=7, grades={(i, "a"): 5 for i in range(1, 8)})
    days = {p.day: p.concepts for p in plans}
    # 种子间隔 1 → 3 → 7：第 1、2、5 天出现，其余天休息
    assert days[1] == ["a"] and days[2] == ["a"] and days[5] == ["a"]
    assert days[3] == [] and days[4] == [] and days[6] == [] and days[7] == []
