# ruff: noqa: E501
"""真实数据 5 折交叉验证：自写 BKT vs pyBKT（Wave 3 任务 3.3）。

协议（两个实现完全一致，只用各自默认初始化，禁止调参掩盖差距）：
  - 按 user_id 的 md5 % 5 分 5 折（确定性，无随机数）；折间用户不重叠
  - 每折：train 用户的所有 (user, skill) 序列拟合；test 用户逐行在线预测
    ——第 t 行的预测只使用同一 (user, skill) 序列中 t 之前 observation
  - 自写 BKT：examdiag.bkt.fit（默认 init .4/.15/.15/.15）+ predict_next
  - pyBKT 1.4.3：Model() 默认参数；predict 的 correct_predictions 即观测前预测
    （源码 docstring 已验证同语义）
  - 指标：AUC（examdiag.eval.auc_score，Mann-Whitney）+ RMSE，跨折汇总

闸门（SPEC）：|AUC 自写 − AUC pyBKT| > 0.05 → 报告写 [STOP] 并创建 STOP 文件；
≤ 0.02 通过；0.02–0.05 继续但标注未达标。结果写 data/real/COMPARE_REPORT.md。

运行：python scripts/compare_bkt.py（必须以文件方式运行：pyBKT 内部用
multiprocessing spawn，不能从 stdin 跑）
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

from examdiag.bkt import fit, predict_next
from examdiag.eval import auc_score, rmse_score

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data/real"
REPORT = DATA / "COMPARE_REPORT.md"
N_FOLDS = 5


def fold_of(user_id: str) -> int:
    return int(hashlib.md5(user_id.encode()).hexdigest(), 16) % N_FOLDS


def load_sequences() -> dict[str, dict[str, list[int]]]:
    """user -> skill -> [0/1]（按 ts 排序）。"""
    q2skill = {}
    with open(DATA / "skills.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            q2skill[r["question_id"]] = r["skill"]
    seqs: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    rows = []
    with open(DATA / "assistments.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            rows.append((r["user_id"], r["ts"], q2skill[r["question_id"]], int(r["correct"])))
    rows.sort(key=lambda x: (x[0], x[1]))
    for uid, _ts, skill, ok in rows:
        seqs[uid][skill].append(ok)
    return seqs


def own_bkt_fold(train_seqs, test_seqs) -> tuple[list[float], list[int]]:
    """按技能拟合 + 在线预测，返回 (preds, truths)。"""
    per_skill_train: dict[str, list[list[int]]] = defaultdict(list)
    for skills in train_seqs.values():
        for sk, seq in skills.items():
            per_skill_train[sk].append(seq)
    preds, truths = [], []
    for skills in test_seqs.values():
        for sk, seq in skills.items():
            if sk not in per_skill_train:
                continue  # 测试折里出现训练折没有的技能：跳过并计数
            import numpy as np

            params = fit([np.asarray(s, dtype=bool) for s in per_skill_train[sk]])
            obs = np.asarray(seq, dtype=bool)
            for t in range(len(seq)):
                preds.append(predict_next(obs[:t], params))
                truths.append(int(obs[t]))
    return preds, truths


def pybkt_fold(fold: int, train_seqs, test_seqs) -> tuple[list[float], list[int], float]:
    from pyBKT.models import Model

    def to_df(seqs) -> pd.DataFrame:
        recs = [
            {"user_id": uid, "skill_name": sk, "correct": ok, "row": i}
            for uid, skills in seqs.items()
            for sk, seq in skills.items()
            for i, ok in enumerate(seq)
        ]
        df = pd.DataFrame(recs)
        return df.sort_values(["user_id", "skill_name", "row"]).reset_index(drop=True)

    train_df, test_df = to_df(train_seqs), to_df(test_seqs)
    t0 = time.time()
    model = Model()
    model.fit(data=train_df)
    fit_s = time.time() - t0
    res = model.predict(data=test_df)
    preds = [float(p) for p in res["correct_predictions"]]
    truths = [int(v) for v in res["correct"]]
    return preds, truths, fit_s


def main() -> None:
    seqs = load_sequences()
    users = sorted(seqs)
    folds = defaultdict(list)
    for u in users:
        folds[fold_of(u)].append(u)

    own_all, py_all = [], []
    rows = ["# ASSISTments 真实数据 5 折 CV：自写 BKT vs pyBKT", "",
            "协议：按用户分折；训练只用各自默认初始化（无调参）；预测为观测前在线预测。", "",
            "| fold | users(train/test) | own AUC | own RMSE | pyBKT AUC | pyBKT RMSE | pyBKT fit(s) |",
            "|---|---|---|---|---|---|---|"]
    for k in range(N_FOLDS):
        test_users = set(folds[k])
        train_seqs = {u: s for u, s in seqs.items() if u not in test_users}
        test_seqs = {u: s for u, s in seqs.items() if u in test_users}

        own_preds, own_truth = own_bkt_fold(train_seqs, test_seqs)
        py_preds, py_truth, fit_s = pybkt_fold(k, train_seqs, test_seqs)
        own_all += list(zip(own_preds, own_truth, strict=True))
        py_all += list(zip(py_preds, py_truth, strict=True))

        o_a = auc_score(own_truth, own_preds)
        o_r = rmse_score(own_truth, own_preds)
        p_a = auc_score(py_truth, py_preds)
        p_r = rmse_score(py_truth, py_preds)
        rows.append(f"| {k} | {len(train_seqs)}/{len(test_seqs)} | {o_a:.4f} | {o_r:.4f} | "
                    f"{p_a:.4f} | {p_r:.4f} | {fit_s:.1f} |")
        print(f"fold {k}: own AUC={o_a:.4f} pyBKT AUC={p_a:.4f}", flush=True)

    own_a = auc_score([t for _, t in own_all], [p for p, _ in own_all])
    own_r = rmse_score([t for _, t in own_all], [p for p, _ in own_all])
    py_a = auc_score([t for _, t in py_all], [p for p, _ in py_all])
    py_r = rmse_score([t for _, t in py_all], [p for p, _ in py_all])
    gap = abs(own_a - py_a)

    verdict = "PASS" if gap < 0.02 else ("WARNING（差距在 0.02–0.05，继续）" if gap <= 0.05 else "STOP")
    rows += ["",
             f"- 汇总：自写 BKT **AUC {own_a:.4f} / RMSE {own_r:.4f}**；"
             f"pyBKT **AUC {py_a:.4f} / RMSE {py_r:.4f}**；AUC 差距 **{gap:.4f}**",
             f"- 预测对数：自写 {len(own_all):,}；pyBKT {len(py_all):,}",
             f"- 闸门（SPEC 3.3）：{'<0.02 通过' if gap < 0.02 else '>0.05 需 STOP' if gap > 0.05 else '0.02–0.05 未达通过线'} → **{verdict}**"]
    REPORT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("\n".join(rows[-4:]))

    if gap > 0.05:
        (ROOT / "STOP").write_text(
            f"AUC gap {gap:.4f} > 0.05 on ASSISTments 5-fold CV\n"
            f"own={own_a:.4f} pyBKT={py_a:.4f}\nsee {REPORT}\n", encoding="utf-8")
        print("[STOP] AUC gap > 0.05 — STOP 文件已创建")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
