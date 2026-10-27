# benchmark — 下次作答预测（AUC / RMSE）

指标：AUC（带并列秩的 Mann-Whitney 自实现，无 sklearn）、RMSE。
协议：在线预测——每一步在观测前给出 P(答对)，观测后把该次作答计入后验。

## 1. 真实数据：ASSISTments skill-builder（corrected，Wave 3）

- 数据：`data/real/assistments.jsonl`，274,590 次作答 / 4,151 用户 / 101 个技能
  （官方 skill_builder_data_corrected.csv 转换，详见 `data/real/CONVERSION_REPORT.md`；
   原始 61.4 MB 经 hf-mirror.com 镜像下载，官方 Google Sites 在本机网络不可达——
   SPEC 5.4 指名的 2012-13 全量（约 340MB）无可达镜像，改用同一官方发布的
   skill-builder corrected 版，即 pyBKT 教程标准对比数据集）。
- 协议：按 user_id 的 md5 % 5 分 5 折（折间用户不重叠）；每折用训练用户拟合、
  测试用户在线预测；两个实现均只用各自默认初始化，**无任何调参**。
- 对比对象：自写 `examdiag.bkt`（纯 numpy，前向 + EM）vs **pyBKT 1.4.3**（默认参数）。
- 完整报告：`data/real/COMPARE_REPORT.md`。

| dataset | model | AUC | RMSE |
|---|---|---|---|
| ASSISTments (real, 5-fold CV) | bkt-ours (EM fit) | **0.7118** | **0.4396** |
| ASSISTments (real, 5-fold CV) | pyBKT 1.4.3 (defaults) | 0.7116 | 0.4397 |

- **AUC 差距 0.0002** —— SPEC 3.3 闸门（< 0.02 通过）**PASS**。
- 分折明细：own 0.7043/0.7037/0.7182/0.7112/0.7218 vs pyBKT 0.7040/0.7037/0.7179/0.7104/0.7223。
- 预测对数：自写 274,576（pyBKT 274,590；差 14 来自个别技能在训练折缺席时按协议跳过）。

## 2. 合成数据（补充基线，Wave 0）

- 数据：`examdiag.eval.generate_benchmark_data` 合成序列，10 概念 × 150 学生 × 12 步，
  前 8 步训练、后 4 步在线预测，seed=0 可复现。此为仓库自造数据，仅用于管线自检。

| dataset | model | AUC | RMSE |
|---|---|---|---|
| synthetic (seed=0) | bkt-ours (EM fit) | 0.7872 | 0.37 |
| synthetic (seed=0) | recent-3 mean | 0.7438 | 0.4162 |
| synthetic (seed=0) | global mean | 0.5 | 0.4567 |

## 运行方式

```bash
python scripts/download_assistments.py   # 3.1 下载（含镜像回退）
python scripts/convert_assistments.py    # 3.2 转换（输出真实统计）
python scripts/compare_bkt.py            # 3.3 5 折 CV + 闸门
```
