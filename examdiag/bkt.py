"""Bayesian Knowledge Tracing: 前向后验更新 + EM 拟合（纯 numpy）。

模型（每个 concept 独立一套参数）：
  状态：L=已掌握，U=未掌握；P(L_1)=p_L0
  转移：U->L 概率 p_T（learn），L 不会退回 U
  发射：P(correct|L)=1-p_S（slip），P(correct|U)=p_G（guess）

推导见 docs/METHOD.md（Wave 3 补全）。实现细节：
  - 前向/后向都做 per-step 归一化（scaled Baum-Welch），防止长序列下溢；
    缩放常数对数之和即 log-likelihood。
  - EM 的 M 步为闭式重估，四参数每轮截断到 [0.01, 0.99]。
  - fit 支持变长序列：按长度分组批量算充分统计量，合并后统一 M 步。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

PARAM_LOW, PARAM_HIGH = 0.01, 0.99


@dataclass(frozen=True)
class BKTParams:
    p_L0: float
    p_T: float
    p_S: float
    p_G: float

    def clipped(self) -> BKTParams:
        return BKTParams(*(float(np.clip(v, PARAM_LOW, PARAM_HIGH)) for v in self.as_array()))

    def as_array(self) -> np.ndarray:
        return np.array([self.p_L0, self.p_T, self.p_S, self.p_G], dtype=float)

    @classmethod
    def from_array(cls, arr) -> BKTParams:
        return cls(*[float(x) for x in arr])


def _check_sequence(seq) -> np.ndarray:
    obs = np.asarray(seq, dtype=bool)
    if obs.ndim != 1:
        raise ValueError(f"sequence must be 1-D 0/1, got shape {obs.shape}")
    return obs


def forward_posterior(sequence, params: BKTParams) -> np.ndarray:
    """每一步的过滤后验 P(L_t | o_1..o_t)，长度与输入相同。"""
    obs = _check_sequence(sequence)
    b_L = np.where(obs, 1.0 - params.p_S, params.p_S)
    b_U = np.where(obs, params.p_G, 1.0 - params.p_G)

    post = np.empty(obs.shape[0])
    p = params.p_L0  # P(L_t) 进入第 t 次观测前的掌握概率
    for t in range(obs.shape[0]):
        a_L = p * b_L[t]
        a_U = (1.0 - p) * b_U[t]
        post[t] = p = a_L / (a_L + a_U)  # 证据更新
        p = post[t] + (1.0 - post[t]) * params.p_T  # 练习转移，供下一步发射
    return post


def predict_next(sequence, params: BKTParams) -> float:
    """P(下一题答对 | 已观察序列)：先转移（learn）再发射。"""
    obs = _check_sequence(sequence)
    p = params.p_L0 if obs.size == 0 else float(forward_posterior(obs, params)[-1])
    p_next = p + (1.0 - p) * params.p_T
    return float(p_next * (1.0 - params.p_S) + (1.0 - p_next) * params.p_G)


# ---------- EM（Baum-Welch） ----------


def _group_by_length(sequences) -> dict[int, np.ndarray]:
    groups: dict[int, list] = defaultdict(list)
    for seq in sequences:
        groups[len(seq)].append(_check_sequence(seq))
    return {n: np.stack(seqs) for n, seqs in groups.items()}


def _group_stats(obs: np.ndarray, p: BKTParams) -> dict[str, float]:
    """一组等长序列 (n, T) 的充分统计量。obs 为 bool 矩阵，1=True=答对。"""
    n, T = obs.shape
    p_L0, p_T, p_S, p_G = p.p_L0, p.p_T, p.p_S, p.p_G

    b_L = np.where(obs, 1.0 - p_S, p_S)  # 发射：已掌握
    b_U = np.where(obs, p_G, 1.0 - p_G)  # 发射：未掌握

    # 前向（缩放）
    alpha_L = np.empty((n, T))
    alpha_U = np.empty((n, T))
    c = np.empty((n, T))
    alpha_L[:, 0] = p_L0 * b_L[:, 0]
    alpha_U[:, 0] = (1.0 - p_L0) * b_U[:, 0]
    c[:, 0] = alpha_L[:, 0] + alpha_U[:, 0]
    alpha_L[:, 0] /= c[:, 0]
    alpha_U[:, 0] /= c[:, 0]
    for t in range(1, T):
        alpha_L[:, t] = (alpha_L[:, t - 1] + p_T * alpha_U[:, t - 1]) * b_L[:, t]
        alpha_U[:, t] = (1.0 - p_T) * alpha_U[:, t - 1] * b_U[:, t]
        c[:, t] = alpha_L[:, t] + alpha_U[:, t]
        alpha_L[:, t] /= c[:, t]
        alpha_U[:, t] /= c[:, t]

    loglik = float(np.log(c).sum())

    # 后向（与前向同一套缩放常数）
    beta_L = np.ones((n, T))
    beta_U = np.ones((n, T))
    for t in range(T - 2, -1, -1):
        beta_L[:, t] = beta_L[:, t + 1] * b_L[:, t + 1] / c[:, t + 1]
        beta_U[:, t] = (
            p_T * beta_L[:, t + 1] * b_L[:, t + 1]
            + (1.0 - p_T) * beta_U[:, t + 1] * b_U[:, t + 1]
        ) / c[:, t + 1]

    gamma_L = alpha_L * beta_L
    gamma_U = alpha_U * beta_U

    # 期望转移数 ξ(U->L) = α_U(t)·p_T·b_L(t+1)·β_L(t+1)/c(t+1)，t 只取 1..T-1
    if T > 1:
        xi_UL = float((alpha_U[:, :-1] * p_T * b_L[:, 1:] * beta_L[:, 1:] / c[:, 1:]).sum())
        gamma_U_pre = float(gamma_U[:, :-1].sum())
    else:
        xi_UL, gamma_U_pre = 0.0, 0.0

    return {
        "n": n,
        "loglik": loglik,
        "gamma_L0": float(gamma_L[:, 0].sum()),
        "N_L": float(gamma_L.sum()),
        "N_U": float(gamma_U.sum()),
        "N_L_wrong": float(gamma_L[:, :][~obs].sum()),
        "N_U_correct": float(gamma_U[:, :][obs].sum()),
        "xi_UL": xi_UL,
        "gamma_U_pre": gamma_U_pre,
    }


def _m_step(stats: dict[str, float], old: BKTParams) -> BKTParams:
    n_total = stats["n"]
    p_L0 = stats["gamma_L0"] / n_total
    p_S = stats["N_L_wrong"] / stats["N_L"] if stats["N_L"] > 0 else old.p_S
    p_G = stats["N_U_correct"] / stats["N_U"] if stats["N_U"] > 0 else old.p_G
    p_T = stats["xi_UL"] / stats["gamma_U_pre"] if stats["gamma_U_pre"] > 0 else old.p_T
    return BKTParams(p_L0, p_T, p_S, p_G).clipped()


def fit(
    sequences,
    init: BKTParams | None = None,
    max_iter: int = 200,
    tol: float = 1e-6,
) -> BKTParams:
    """EM 拟合四参数；log-likelihood 相对变化 < tol 或达到 max_iter 停止。"""
    groups = _group_by_length(sequences)
    if not groups:
        raise ValueError("no sequences to fit")
    params = init or BKTParams(p_L0=0.4, p_T=0.15, p_S=0.15, p_G=0.15)
    prev_ll = -np.inf
    for _ in range(max_iter):
        acc = {"n": 0.0, "loglik": 0.0, "gamma_L0": 0.0, "N_L": 0.0, "N_U": 0.0,
               "N_L_wrong": 0.0, "N_U_correct": 0.0, "xi_UL": 0.0, "gamma_U_pre": 0.0}
        for obs in groups.values():
            for key, val in _group_stats(obs, params).items():
                acc[key] += val
        loglik = acc["loglik"]
        params = _m_step(acc, params)
        if abs(loglik - prev_ll) < tol * max(1.0, abs(loglik)):
            break
        prev_ll = loglik
    return params


def log_likelihood(sequences, params: BKTParams) -> float:
    return float(sum(_group_stats(obs, params)["loglik"] for obs in _group_by_length(sequences).values()))


def simulate(params: BKTParams, n_students: int, seq_len: int, seed: int = 0) -> np.ndarray:
    """按 BKT 生成 (n_students, seq_len) 的 0/1 作答矩阵，用于自检与评估。"""
    rng = np.random.default_rng(seed)
    obs = np.empty((n_students, seq_len), dtype=bool)
    learned = rng.random(n_students) < params.p_L0
    for t in range(seq_len):
        p_correct = np.where(learned, 1.0 - params.p_S, params.p_G)
        obs[:, t] = rng.random(n_students) < p_correct
        learned = learned | (rng.random(n_students) < params.p_T)
    return obs
