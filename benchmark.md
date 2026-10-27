# benchmark — 下次作答预测（合成数据基线）

- 数据：`examdiag.eval.generate_benchmark_data` 合成序列，10 概念 × 150 学生 × 12 步，前 8 步训练、后 4 步在线预测（每步观测前给出 P(答对)），seed=0 可复现。
- 指标：AUC（带并列秩的 Mann-Whitney 实现）、RMSE。
- 数据集说明：按 SPEC 5.4 允许的路径使用仓库内自造合成序列；ASSISTments 真实数据下载与 pyBKT 交叉比对留待后续 Wave。

| model | AUC | RMSE |
|---|---|---|
| bkt-ours (EM fit) | 0.7872 | 0.37 |
| recent-3 mean | 0.7438 | 0.4162 |
| global mean | 0.5 | 0.4567 |
