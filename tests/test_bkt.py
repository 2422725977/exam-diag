import numpy as np
import pytest

from examdiag.bkt import (
    BKTParams,
    _group_stats,
    fit,
    forward_posterior,
    log_likelihood,
    predict_next,
    simulate,
)

TRUE = BKTParams(p_L0=0.3, p_T=0.1, p_S=0.1, p_G=0.2)


# ---------- 前向后验 ----------


def test_all_correct_raises_posterior_toward_high_value():
    post = forward_posterior([1, 1, 1, 1, 1], TRUE)
    assert post[0] > TRUE.p_L0
    assert np.all(np.diff(post) > 0)
    assert post[-1] > 0.85


def test_wrong_answer_drops_posterior():
    post = forward_posterior([1, 1, 0], TRUE)
    assert post[2] < post[1]
    # 答错但仍高于未作答时的先验：slip 有限
    assert post[2] > 0.3


def test_posterior_stays_in_unit_interval_on_long_sequence():
    rng = np.random.default_rng(7)
    seq = rng.integers(0, 2, size=200)
    post = forward_posterior(seq, TRUE)
    assert np.all((post >= 0) & (post <= 1))


def test_predict_next_between_emission_bounds():
    seq = [1, 1, 1, 0, 1]
    pred = predict_next(seq, TRUE)
    assert TRUE.p_G - 1e-9 <= pred <= 1 - TRUE.p_S + 1e-9
    # 连续答对后的预测应高于初始正确率
    assert predict_next([1] * 5, TRUE) > (1 - TRUE.p_S) * 0.5 + TRUE.p_G * 0.5


# ---------- EM 充分统计量 ----------


def _reference_fb(seq, p: BKTParams):
    """无缩放的标量前向-后向参照实现，用于交叉验证批量实现。"""
    T = len(seq)
    b = [(1 - p.p_S, p.p_S) if x else (p.p_G, 1 - p.p_G) for x in seq]  # (P(o|L), P(o|U))
    alpha = np.empty((T, 2))
    alpha[0] = [p.p_L0 * b[0][0], (1 - p.p_L0) * b[0][1]]
    for t in range(1, T):
        alpha[t, 0] = (alpha[t - 1, 0] + p.p_T * alpha[t - 1, 1]) * b[t][0]
        alpha[t, 1] = (1 - p.p_T) * alpha[t - 1, 1] * b[t][1]
    ll = alpha[-1].sum()
    beta = np.ones((T, 2))
    for t in range(T - 2, -1, -1):
        beta[t, 0] = b[t + 1][0] * beta[t + 1, 0]
        beta[t, 1] = p.p_T * b[t + 1][0] * beta[t + 1, 0] + (1 - p.p_T) * b[t + 1][1] * beta[t + 1, 1]
    gamma = alpha * beta / ll  # 平滑后验 P(state_t | 整条序列)
    return float(np.log(ll)), gamma


def test_group_stats_matches_reference_forward_backward():
    obs = np.array([[1, 1, 0, 1], [0, 1, 1, 1]], dtype=bool)
    stats = _group_stats(obs, TRUE)
    ll_ref = sum(_reference_fb(seq, TRUE)[0] for seq in obs)
    g0_ref = sum(_reference_fb(seq, TRUE)[1][0, 0] for seq in obs)
    assert stats["loglik"] == pytest.approx(ll_ref, rel=1e-9)
    # EM 用的是平滑后验，所以 gamma_L0 不等于过滤后验之和
    assert stats["gamma_L0"] == pytest.approx(g0_ref, rel=1e-9)
    # 每步 gamma_L + gamma_U = 1，聚合即 N_L + N_U = n*T
    assert stats["N_L"] + stats["N_U"] == pytest.approx(obs.size)


def test_log_likelihood_improves_with_fitting():
    obs = simulate(TRUE, n_students=200, seq_len=20, seed=3)
    seqs = list(obs)
    wrong = BKTParams(p_L0=0.9, p_T=0.01, p_S=0.4, p_G=0.01)
    ll_before = log_likelihood(seqs, wrong)
    fitted = fit(seqs, init=wrong)
    ll_after = log_likelihood(seqs, fitted)
    assert ll_after > ll_before


# ---------- 参数恢复（Wave 0 验收硬指标） ----------


def test_em_recovers_true_params():
    """真实参数生成 2000 条长度 30 的序列，EM 拟合后每个参数误差 < 0.05。"""
    seqs = list(simulate(TRUE, n_students=2000, seq_len=30, seed=42))
    fitted = fit(seqs, init=BKTParams(p_L0=0.4, p_T=0.15, p_S=0.15, p_G=0.15))
    errs = np.abs(fitted.as_array() - TRUE.as_array())
    for name, err in zip(("p_L0", "p_T", "p_S", "p_G"), errs):
        assert err < 0.05, f"{name}: fitted={getattr(fitted, name):.4f} err={err:.4f}"


def test_em_recovers_params_from_variable_length_sequences():
    rng = np.random.default_rng(11)
    seqs = list(simulate(TRUE, n_students=1200, seq_len=30, seed=1))
    # 随机截断成长度 5..30 的变长序列
    short = [seq[: rng.integers(5, 31)] for seq in seqs[:800]]
    fitted = fit(short, init=BKTParams(p_L0=0.4, p_T=0.2, p_S=0.2, p_G=0.2))
    assert np.abs(fitted.as_array() - TRUE.as_array()).max() < 0.05


def test_fit_respects_param_bounds():
    # 极端初始化也不允许参数跑出 [0.01, 0.99]
    seqs = list(simulate(TRUE, n_students=100, seq_len=10, seed=5))
    fitted = fit(seqs, init=BKTParams(p_L0=0.99, p_T=0.99, p_S=0.01, p_G=0.01))
    assert np.all(fitted.as_array() >= 0.01 - 1e-12)
    assert np.all(fitted.as_array() <= 0.99 + 1e-12)


def test_fit_rejects_empty_input():
    with pytest.raises(ValueError):
        fit([])
