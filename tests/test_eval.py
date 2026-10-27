import numpy as np
import pytest

from examdiag.eval import (
    auc_score,
    format_markdown,
    generate_benchmark_data,
    rmse_score,
    run_benchmark,
)

# ---------- 指标实现 ----------


def test_auc_perfect_and_inverted():
    assert auc_score([1, 0], [0.9, 0.1]) == pytest.approx(1.0)
    assert auc_score([1, 0], [0.1, 0.9]) == pytest.approx(0.0)


def test_auc_ties_score_half():
    assert auc_score([1, 0], [0.5, 0.5]) == pytest.approx(0.5)


def test_auc_matches_pairwise_counting():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 50)
    s = rng.random(50)
    # 直接数正负样本对的胜率
    wins = sum(
        1.0 if s[i] > s[j] else 0.5 if s[i] == s[j] else 0.0
        for i in range(50)
        for j in range(50)
        if y[i] == 1 and y[j] == 0
    )
    n_pos, n_neg = int(y.sum()), 50 - int(y.sum())
    assert auc_score(y, s) == pytest.approx(wins / (n_pos * n_neg))


def test_auc_rejects_single_class():
    with pytest.raises(ValueError):
        auc_score([1, 1], [0.3, 0.7])


def test_rmse_known_value():
    assert rmse_score([1, 0, 1], [0.5, 0.5, 0.5]) == pytest.approx(0.5)


# ---------- 数据与基准 ----------


def test_generated_data_is_deterministic_and_shaped():
    d1 = generate_benchmark_data(n_concepts=3, n_students=20, seq_len=10, seed=1)
    d2 = generate_benchmark_data(n_concepts=3, n_students=20, seq_len=10, seed=1)
    assert set(d1) == {0, 1, 2}
    for c in d1:
        assert d1[c].shape == (20, 10)
        assert d1[c].dtype == np.dtype(bool)
        assert np.array_equal(d1[c], d2[c])


def test_benchmark_bkt_beats_threshold_and_baselines():
    """验收硬指标：自写 BKT 在合成基准上 AUC > 0.65，且优于两个基线。"""
    rows = run_benchmark()
    by_name = {r["model"]: r for r in rows}
    assert by_name["bkt-ours (EM fit)"]["auc"] > 0.65
    assert by_name["bkt-ours (EM fit)"]["auc"] > by_name["recent-3 mean"]["auc"]
    assert by_name["bkt-ours (EM fit)"]["auc"] > by_name["global mean"]["auc"]
    assert by_name["bkt-ours (EM fit)"]["rmse"] < 0.5


def test_markdown_table_contains_real_numbers():
    rows = run_benchmark(n_concepts=3, n_students=30)
    md = format_markdown(rows)
    assert "| model | AUC | RMSE |" in md
    assert str(rows[0]["auc"]) in md
