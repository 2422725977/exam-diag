"""Next-response prediction benchmark: AUC / RMSE.

协议（SPEC 5.4）：合成多概念答题序列，每条序列前 train_len 次作答用于拟合
（按概念聚合 fit EM），余下部分做在线预测——每一步在观测前给出 P(答对)，
观测后把该次作答计入后验继续走。不依赖 scikit-learn，AUC 用带并列秩的
Mann-Whitney U 实现。

ASSISTments 真实数据集的下载与比对留给后续 Wave；本文件按 SPEC 允许的
路径用仓库内合成序列（seed 固定，可复现）跑通基线。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .bkt import BKTParams, fit, predict_next

DEFAULT_TRAIN_LEN = 8
DEFAULT_SEQ_LEN = 12


def auc_score(y_true, y_score) -> float:
    """带并列平均秩的 AUC（Mann-Whitney U 统计量的归一化形式）。"""
    y_true = np.asarray(y_true, dtype=bool)
    y_score = np.asarray(y_score, dtype=float)
    n_pos = int(y_true.sum())
    n_neg = y_true.size - n_pos
    if n_pos == 0 or n_neg == 0:
        raise ValueError("AUC undefined when only one class is present")
    order = np.argsort(y_score, kind="mergesort")
    sx = y_score[order]
    ranks = np.empty(sx.size)
    i = 0
    while i < sx.size:
        j = i
        while j + 1 < sx.size and sx[j + 1] == sx[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    rank_sum_pos = ranks[y_true].sum()
    return float((rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def rmse_score(y_true, y_score) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_score = np.asarray(y_score, dtype=float)
    return float(np.sqrt(np.mean((y_score - y_true) ** 2)))


def generate_benchmark_data(
    n_concepts: int = 10,
    n_students: int = 150,
    seq_len: int = DEFAULT_SEQ_LEN,
    seed: int = 0,
) -> dict[int, np.ndarray]:
    """按概念生成 (n_students, seq_len) 的 0/1 矩阵。

    每个概念一套真实 BKT 参数（随机采样），每个学生叠加一个能力偏移
    （改变其 p_L0），制造跨学生异质性——这是预测任务有区分度的来源。
    """
    rng = np.random.default_rng(seed)
    data: dict[int, np.ndarray] = {}
    for c in range(n_concepts):
        p_T = rng.uniform(0.05, 0.25)
        p_S = rng.uniform(0.05, 0.20)
        p_G = rng.uniform(0.10, 0.35)
        p_L0_base = rng.uniform(0.20, 0.60)
        ability = rng.normal(0.0, 0.18, size=n_students)
        p_L0 = np.clip(p_L0_base + ability, 0.05, 0.90)

        obs = np.empty((n_students, seq_len), dtype=bool)
        learned = rng.random(n_students) < p_L0
        for t in range(seq_len):
            p_correct = np.where(learned, 1.0 - p_S, p_G)
            obs[:, t] = rng.random(n_students) < p_correct
            learned = learned | (rng.random(n_students) < p_T)
        data[c] = obs
    return data


def _recent_mean_prefix(seq: np.ndarray, t: int, k: int, fallback: float) -> float:
    """t 时刻之前最近 k 次作答的正确率；无历史时用全局均值兜底。"""
    history = np.asarray(seq[max(0, t - k) : t], dtype=float)
    return float(history.mean()) if history.size else fallback


def run_benchmark(
    n_concepts: int = 10,
    n_students: int = 150,
    seq_len: int = DEFAULT_SEQ_LEN,
    train_len: int = DEFAULT_TRAIN_LEN,
    seed: int = 0,
) -> list[dict[str, float | str]]:
    """返回 benchmark 表行：model × AUC × RMSE。"""
    if not 0 < train_len < seq_len:
        raise ValueError("need 0 < train_len < seq_len")
    data = generate_benchmark_data(n_concepts, n_students, seq_len, seed)

    # 每个概念只用训练段拟合参数
    fitted: dict[int, BKTParams] = {}
    global_train_rate = float(
        np.mean([obs[:, :train_len].mean() for obs in data.values()])
    )
    for c, obs in data.items():
        fitted[c] = fit(list(obs[:, :train_len]))

    y_true: list[float] = []
    y_bkt: list[float] = []
    y_global: list[float] = []
    y_recent: list[float] = []
    for c, obs in data.items():
        params = fitted[c]
        for seq in obs:
            for t in range(train_len, seq_len):
                y_true.append(float(seq[t]))
                y_bkt.append(predict_next(seq[:t], params))
                y_global.append(global_train_rate)
                y_recent.append(_recent_mean_prefix(seq, t, k=3, fallback=global_train_rate))

    rows = []
    for name, scores in (
        ("bkt-ours (EM fit)", y_bkt),
        ("recent-3 mean", y_recent),
        ("global mean", y_global),
    ):
        rows.append(
            {
                "model": name,
                "auc": round(auc_score(y_true, scores), 4),
                "rmse": round(rmse_score(y_true, scores), 4),
            }
        )
    return rows


def format_markdown(rows: list[dict[str, float | str]]) -> str:
    lines = [
        "# benchmark — 下次作答预测（合成数据基线）",
        "",
        "- 数据：`examdiag.eval.generate_benchmark_data` 合成序列，10 概念 × 150 学生 × 12 步，"
        "前 8 步训练、后 4 步在线预测（每步观测前给出 P(答对)），seed=0 可复现。",
        "- 指标：AUC（带并列秩的 Mann-Whitney 实现）、RMSE。",
        "- 数据集说明：按 SPEC 5.4 允许的路径使用仓库内自造合成序列；ASSISTments 真实数据"
        "下载与 pyBKT 交叉比对留待后续 Wave。",
        "",
        "| model | AUC | RMSE |",
        "|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['model']} | {r['auc']} | {r['rmse']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    rows = run_benchmark()
    text = format_markdown(rows)
    out = Path(__file__).resolve().parent.parent / "benchmark.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"written to {out}")


if __name__ == "__main__":
    main()
