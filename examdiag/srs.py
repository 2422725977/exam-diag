"""间隔重复复习调度（Wave 1 任务 1.3 + SM-2 变体扩展）。

两层 API：
  - plan_week：原轻量版——按根因掌握度排 7 天序列，interval = max(1, round(SPAN·m))；
  - sm2_plan：SM-2 变体完整调度器——EF 由掌握度初始化，按每日作答质量(0-5)调
    整 easiness，间隔按种子序列递增后乘 EF 增长，每日队列上限超员自动顺延。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .diagnose import Diagnosis

SPAN = 6.0  # interval = max(1, round(SPAN * mastery))，根因 mastery < 0.5 → interval <= 3


@dataclass
class DayPlan:
    day: int
    concepts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"day": self.day, "concepts": self.concepts}


def plan_week(diagnosis: Diagnosis, horizon: int = 7, span: float = SPAN) -> list[DayPlan]:
    schedule: dict[int, set[str]] = defaultdict(set)
    for rc in diagnosis.root_causes:
        interval = max(1, round(span * rc.mastery))
        day = 1
        while day <= horizon:
            schedule[day].add(rc.concept_id)
            day += interval
    plans = []
    for day in range(1, horizon + 1):
        ids = schedule.get(day, set())
        plans.append(
            DayPlan(
                day=day,
                concepts=sorted(ids, key=lambda cid: (diagnosis.mastery.get(cid, 0.0), cid)),
            )
        )
    return plans


# ---------- SM-2 变体 ----------

SEED_INTERVALS = (1, 3, 7)  # 前几次连续成功使用的固定间隔，之后按 EF 增长
EF_MIN, EF_MAX = 1.3, 2.8


@dataclass
class SM2Item:
    concept_id: str
    easiness: float = 2.5  # EF，≥ EF_MIN
    interval: int = 0
    reps: int = 0
    due_day: int = 1
    deferrals: int = 0  # 被每日上限顺延的次数（老化计数，防饿死）


@dataclass
class SM2Config:
    max_per_day: int = 20
    horizon: int = 7


def ef_from_mastery(mastery: float, ef_min: float = EF_MIN, ef_max: float = EF_MAX) -> float:
    """掌握度 → 初始 easiness：掌握越好间隔长得越快。"""
    return ef_min + (ef_max - ef_min) * min(max(mastery, 0.0), 1.0)


def sm2_review(
    item: SM2Item, grade: int, ef_min: float = EF_MIN, ef_max: float = EF_MAX
) -> SM2Item:
    """SM-2 一步复习更新：grade ∈ 0..5（5=秒答，<3 视为没记住）。

    - EF 调整：EF' = EF + (0.1 - (5-q)·(0.08 + (5-q)·0.02))，截断到 [EF_MIN, EF_MAX]；
    - q < 3：连续成功清零，间隔回 1（明天重来）；
    - q ≥ 3：reps+1，间隔按种子序列 (1,3,7) 递增，之后 interval = round(interval·EF)。
    """
    q = min(max(grade, 0), 5)
    ef = item.easiness + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ef = min(max(ef, ef_min), ef_max)
    if q < 3:
        return SM2Item(item.concept_id, ef, 1, 0, item.due_day + 1, 0)
    reps = item.reps + 1
    if reps <= len(SEED_INTERVALS):
        interval = SEED_INTERVALS[reps - 1]
    else:
        interval = max(1, round(item.interval * ef))
    return SM2Item(item.concept_id, ef, interval, reps, item.due_day + interval)


def _default_grade(mastery: float) -> int:
    """无逐日作答质量时的确定性缺省 grade（由掌握度映射）。"""
    if mastery < 0.3:
        return 2
    if mastery < 0.5:
        return 3
    return 4


def sm2_plan(
    diagnosis: Diagnosis,
    horizon: int = 7,
    max_per_day: int = 20,
    grades: dict[tuple[int, str], int] | None = None,
) -> list[DayPlan]:
    """SM-2 调度：根因为初始队列，返回 horizon 天的每日概念序列。

    - 每个根因的 EF 由其掌握度初始化（越弱 EF 越低、间隔长得越慢）；
    - 每天先收"到期项"，超过 max_per_day 的顺延到次日；
    - 排序 = 老化优先（顺延次数多的先出队）再按掌握度升序——防止天天失败的
      弱项把被顺延的强项永久挤出队列（测试驱动的修复）；
    - grades[(day, concept_id)] 可注入每日复习质量（0-5）做模拟；
      缺省用掌握度映射的确定性 grade。
    """
    cfg_grades = grades or {}
    items = {
        rc.concept_id: SM2Item(rc.concept_id, ef_from_mastery(rc.mastery), due_day=1)
        for rc in diagnosis.root_causes
    }
    plans: list[DayPlan] = []
    for day in range(1, horizon + 1):
        due = sorted(
            (it for it in items.values() if it.due_day == day),
            key=lambda it: (-it.deferrals,
                            diagnosis.mastery.get(it.concept_id, 0.0), it.concept_id),
        )
        today, deferred = due[:max_per_day], due[max_per_day:]
        for it in deferred:
            it.due_day = day + 1
            it.deferrals += 1
        for it in today:
            g = cfg_grades.get(
                (day, it.concept_id),
                _default_grade(diagnosis.mastery.get(it.concept_id, 0.0)),
            )
            items[it.concept_id] = sm2_review(it, g)
        plans.append(DayPlan(day=day, concepts=[it.concept_id for it in today]))
    return plans
