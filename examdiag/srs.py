"""间隔重复复习调度（Wave 1 任务 1.3）。

按根因掌握度生成未来 7 天的每日复习序列：
- 第 1 天复习全部根因，同一天内掌握度最低的排最前（最弱先补）；
- 之后按间隔 repeats：interval = max(1, round(SPAN * mastery))，
  掌握度越低间隔越短、7 天内出现越频繁（"间隔按 mastery 反比"的离散实现）。
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
