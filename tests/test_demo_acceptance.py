"""Wave 1 验收：demo 数据上诊断出的第 1 个根因必须是 ds.tree.traverse（SPEC 1.6）。"""

from pathlib import Path

import pytest

from examdiag.diagnose import diagnose
from examdiag.schema import load_attempts, load_concepts, load_questions

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "data/demo_attempts.jsonl"

pytestmark = pytest.mark.skipif(
    not DEMO.exists(), reason="data/demo_attempts.jsonl not generated yet"
)


@pytest.fixture(scope="module")
def demo_diagnosis():
    concepts = load_concepts(ROOT / "data/concepts/408.yaml")
    questions = load_questions(ROOT / "data/questions/408.jsonl")
    attempts = load_attempts(DEMO)
    return diagnose(attempts, questions, concepts), attempts


def test_demo_first_root_cause_is_tree_traverse(demo_diagnosis):
    d, _ = demo_diagnosis
    assert d.root_causes, "demo 数据必须产出根因"
    assert d.root_causes[0].concept_id == "ds.tree.traverse"


def test_demo_rotate_failures_explained_by_traverse(demo_diagnosis):
    """植入的『BST 旋转连续错』必须被归因为 traverse 的下游症状，而非独立根因。"""
    d, _ = demo_diagnosis
    ids = [r.concept_id for r in d.root_causes]
    assert "ds.bst.rotate" not in ids
    assert "ds.bst.rotate" in d.root_causes[0].explains


def test_demo_remedy_path_goes_through_prereq_chain(demo_diagnosis):
    d, _ = demo_diagnosis
    path = d.root_causes[0].remedy_path
    assert path[0] == "ds.tree.traverse"
    assert "ds.bst.rotate" in path  # 补习路径覆盖到旋转


def test_demo_prereqs_stay_mastered(demo_diagnosis):
    d, _ = demo_diagnosis
    for cid in ("ds.stack.stack", "ds.recursion", "ds.tree.binary"):
        assert d.mastery[cid] > 0.5, f"{cid} 应保持掌握（demo 植入为答对）"
    assert d.mastery["ds.tree.traverse"] < 0.5


def test_demo_attempt_count(demo_diagnosis):
    _, attempts = demo_diagnosis
    assert len(attempts) == 500
    assert {a.user_id for a in attempts} == {"demo-user"}
