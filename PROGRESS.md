# PROGRESS — exam-diag Wave 0

所有数字均为真实命令的真实输出，不许写"预计"。

## 0.8 bootstrap：仓库初始化（2026-10-28）

执行环境：macOS (darwin 27.0.0 arm64)，gh 已登录账号 `2422725977`。

```
$ gh repo view exam-diag --json name,visibility,url,description
{"description":"Find the root-cause concept behind every wrong answer — a knowledge-tracing diagnostic engine for exam mistakes.","name":"exam-diag","url":"https://github.com/2422725977/exam-diag","visibility":"PUBLIC"}

$ gh repo view exam-diag --json repositoryTopics,licenseInfo
{"licenseInfo":{"key":"mit","name":"MIT License"},"repositoryTopics":["bayesian-knowledge-tracing","education","exam","knowledge-tracing","learning-analytics","python","spaced-repetition"]}

$ git remote -v
origin	git@github.com:2422725977/exam-diag.git (fetch)
origin	git@github.com:2422725977/exam-diag.git (push)
```

- LICENSE：MIT，Copyright (c) 2026 Xin Xia，GitHub 已识别为 `MIT License`。
- README.md：极简英文 10 行版（按 SPEC 8.3），完整版留给 Wave 2。
- commit 身份：`user.name=xi` / `user.email=70122327+2422725977@users.noreply.github.com`（GitHub noreply 地址，用于贡献图认领）。

验收：`"visibility":"PUBLIC"` ✓，description 非空 ✓，7 个 topics 全部打上 ✓。

## 0.1 + 0.2 skeleton：包骨架与 schema（2026-10-28）

产出：`pyproject.toml`（依赖 numpy/pydantic/pyyaml，dev 加 pytest/ruff/networkx，含 ruff 与 pytest 配置）、`examdiag/__init__.py`、`examdiag/schema.py`（Concept/Question/Attempt/ConceptGraph 四模型 + prereq 未知引用校验 + DFS 环检测并报具体环路 + YAML/JSONL 加载器）、`examdiag/cli.py`（argparse 骨架，`diagnose` 子命令 Wave 1 落地）。

```
$ pip install -e .
Successfully built exam-diag
Successfully installed exam-diag-0.1.0

$ python -c "import examdiag; print('import examdiag OK, version', examdiag.__version__)"
import examdiag OK, version 0.1.0

$ examdiag --version
examdiag 0.1.0

$ ruff check .
All checks passed!

$ python -m pytest tests/ -q
.......................                                                  [100%]
23 passed in 0.06s
```

验收：`import examdiag` 无报错 ✓；`pytest tests/test_schema.py` 23 passed 全绿 ✓（含环检测、未知 prereq、difficulty/id/subject 边界、三类文件加载）。

## 0.5 bkt.py：前向后验 + EM 拟合（2026-10-28）

产出：`examdiag/bkt.py`（纯 numpy）——`forward_posterior`（过滤后验）、`predict_next`（先转移再发射的下次答对概率）、`fit`（缩放 Baum-Welch EM，支持变长序列按长度分批，M 步闭式重估 + [0.01,0.99] 截断，收敛阈值相对变化 <1e-6 或 200 轮）、`log_likelihood`、`simulate`（合成数据生成器）。

**参数恢复验收**（真实参数 p_L0=.3, p_T=.1, p_S=.1, p_G=.2 生成 2000 条长度 30 的序列，seed=42，初值 (.4,.15,.15,.15)）：

```
$ python -m pytest tests/test_bkt.py -q
10 passed

fitted: p_L0=0.3118  p_T=0.0930  p_S=0.1029  p_G=0.1978
abs err: [0.0118, 0.0070, 0.0029, 0.0022]   # 四参数全部 < 0.05 ✓
```

正确性交叉验证：测试内置无缩放标量前向-后向参照实现，与批量缩放实现的 log-likelihood 与平滑后验一致（rel 1e-9）。变长序列恢复测试同样通过。

```
$ python -m pytest tests/ -q
.................................                                        [100%]
33 passed in 0.32s
$ ruff check .
All checks passed!
```

## 0.6 eval.py：AUC / RMSE 基线（2026-10-28）

产出：`examdiag/eval.py` —— 合成多概念序列（10 概念 × 150 学生 × 12 步，每概念真实 BKT 参数随机采样 + 每学生能力偏移制造异质性），前 8 步按概念 EM 拟合、后 4 步在线预测（每步观测前给 P(答对)）；AUC 为带并列秩的 Mann-Whitney 自实现（无 sklearn）；对比基线：近 3 次均值、全局均值。运行 `python -m examdiag.eval` 生成 `benchmark.md`。

```
$ python -m examdiag.eval
| model | AUC | RMSE |
|---|---|---|
| bkt-ours (EM fit) | 0.7872 | 0.37 |
| recent-3 mean | 0.7438 | 0.4162 |
| global mean | 0.5 | 0.4567 |
```

验收：AUC 0.7872 > 0.65 ✓，且优于两个基线；RMSE 0.37。数据集说明：按 SPEC 5.4 允许路径使用仓库内合成序列（seed=0 可复现），ASSISTments 下载与 pyBKT 交叉比对留待后续 Wave，未冒充真实数据。

```
$ python -m pytest tests/test_eval.py -q
8 passed
```

## 0.3 四科知识点 240 个（2026-10-28）

产出：`data/concepts/{408,math1,english,politics}.yaml` 各恰好 60 节点 + `scripts/validate_data.py` 验收脚本。

| 科目 | 节点 | 根节点 | 依赖边 | 最长链 | 结构说明 |
|---|---|---|---|---|---|
| 408 | 60 | 10 | 60 | 8 层 | 数据结构 30 + 组成 10 + 操作系统 10 + 网络 10，严格前置链（栈→递归→树遍历→BST→AVL） |
| math1 | 60 | 4 | 77 | 12 层 | 高数 30 + 线代 15 + 概率 15；跨块弱耦合仅 2 条人工确认边（连续型分布←定积分、偏导←向量） |
| english | 60 | 39 | 29 | 5 层 | 能力层级图：词汇 25 → 句法 20 → 篇章 15，根节点 39 ≤ 40 达标 |
| politics | 60 | 6 | 56 | 12 层 | 马原 20（前置边建全）+ 毛中特 14 + 史纲 12（按时间线性，深度即来自此链）+ 思修 14 |

```
$ python scripts/validate_data.py concepts data/concepts/408.yaml --subject 408
[PASS] schema 加载（含 prereq 引用与无环） / 节点数 == 60 / subject 一致 / 无孤立节点
       stats: nodes=60 roots=10 sinks=27 depth=8 edges=60
# math1/english/politics 同样全 PASS；跨文件 concept id 唯一 PASS
RESULT: all checks PASSED
```

验收：四科各恰好 60 节点 ✓；408/math1/politics 无环且无孤立节点 ✓；english 根节点 39 ≤ 40 ✓；跨文件 id 唯一 ✓。说明：english 为能力层级图（非全连接 DAG），按要求允许大量 prereqs 为空；politics 最长链 12 来自史纲线性时间轴（SPEC 明确要求"史纲按时间线性"）。

## 0.4 四科题目 600 道（2026-10-28）

产出：`data/questions/{408,math1,english,politics}.jsonl` 各恰好 150 行。每科分 6 批 × 25 道追加生成，每批 `wc -l` 确认；全部 `source: "self-built"`（未编造任何真题题号）；每题 1-2 个 concept（主概念排第一）。

| 科目 | 行数 | 概念覆盖 | 结构说明 |
|---|---|---|---|
| 408 | 150 | 60/60 | 数据结构 75（含 8+ 道数字推演题）+ 组成 25 + 操作系统 25 + 网络 25 |
| math1 | 150 | 60/60（每概念 ≥2 次） | 高数 75 / 线代 40 / 概率 35；30 余道计算题经独立数值/符号验算 |
| english | 150 | 60/60 | 完形 35 / 语法长难句 45 / 词汇辨析 30 / 阅读 40（短文 40-90 词） |
| politics | 150 | 60/60（每概念 ≥2 次） | 马原 62 道（41.3% ≥ 40% 达标）+ 毛中特 34 + 史纲 24 + 思修 30 |

```
$ python scripts/validate_data.py all        # 四科概念 + 四科题目 + 跨文件 id 唯一
== concepts: 408.yaml / math1.yaml / english.yaml / politics.yaml
== questions: 408.jsonl / math1.jsonl / english.jsonl / politics.jsonl
RESULT: all checks PASSED
```

答案质量复核：408 抽 7 道可推演题用独立程序重算全一致（如 q408-001 行优先地址 1132、q408-052 折半 ASL=25/9、q408-130 CRC=101）；math1 代理用 Python 数值/符号方法验算 30+ 题后 0 处需修正；english/politics 逐题人工核对唯一正确项（politics 干扰项均为教材常见易混表述）。

## Wave 0 完成情况（2026-10-28）

| 任务 | 实际产出 | 验收 | 未完成项与原因 |
|---|---|---|---|
| 0.1 包初始化 | pyproject + examdiag 包 | `import examdiag` OK；`pip install -e .` 成功 | 无 |
| 0.2 schema | Concept/Question/Attempt/ConceptGraph + 环检测 | test_schema.py 23 passed | 无 |
| 0.3 知识点 | 4 科 × 60 = 240 节点 | `validate_data.py concepts` 四科全 PASS；跨文件 id 唯一 | 无 |
| 0.4 题库 | 4 科 × 150 = 600 道（未降级） | `validate_data.py all` 全 PASS | 无 |
| 0.5 BKT 引擎 | 前向后验 + 缩放 EM（纯 numpy） | 合成数据恢复误差 [0.0118, 0.0070, 0.0029, 0.0022] 全部 < 0.05 | 无 |
| 0.6 评估 | benchmark.md | BKT AUC **0.7872** > 0.65，优于两个基线；RMSE 0.37 | ASSISTments 真实数据下载与 pyBKT 交叉比对按计划留待后续 Wave |
| 0.7 PROGRESS | 本文件（真实命令与真实数字） | — | 无 |
| 0.8 GitHub | 公开仓库 2422725977/exam-diag | `"visibility":"PUBLIC"`、description/topics/LICENSE 齐、每步 commit 即推 | 无 |

- 测试基线：`pytest tests/ -q` → **41 passed**；`ruff check .` → All checks passed。
- 执行说明：每完成一步即 commit + push（增量上传）；题库由子代理按科目串行生成（环境并发上限为 1），主会话逐科复核后提交。
- Wave 1 待办：graph.py / diagnose.py / srs.py / cli.py、demo_attempts.jsonl 与根因诊断验收。
