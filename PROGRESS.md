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

## Wave 1（2026-10-28）：诊断能力

| 任务 | 产出 | 验收 |
|---|---|---|
| 1.1 graph.py | networkx DAG：拓扑序/祖先闭包/最短路径/环检测，方向统一 前置→后继 | test_graph.py 8 passed |
| 1.2 diagnose.py | SPEC 5.3 算法：概念级 BKT 拟合 → mastery；score(c)=(1-m)·Π(1-m_a)^(1/d)；症状过滤（有未掌握前置→是症状）→ mastery 升序+拓扑序取 top-3；insufficient_data（<3 次）边界 | test_diagnose.py 12 passed |
| 1.3 srs.py | 未来 7 天每日复习序列，interval=max(1, round(6·mastery))（间隔与 mastery 反比），Day 1 全根因、最弱优先 | test_srs.py 6 passed |
| 1.4 cli.py | `examdiag diagnose --attempts --concepts [--questions/--user/--top/--plan/--json]`，rich 彩色表格；concepts/questions 支持目录、questions 缺省自动发现 | test_cli.py 6 passed |
| 1.5 demo 数据 | `data/demo_attempts.jsonl` 500 条（生成器 `scripts/make_demo_attempts.py`，seed 固定）：结尾 rotate×6+delete×4 连续错，traverse 先对3后连错5，前置（栈/递归/二叉树）掌握，其余 464 条 80% 正确填充 | 行数 500 ✓ |
| 1.6 验收测试 | 断言 demo 第一根因 = `ds.tree.traverse`；rotate 只作为其下游症状出现 | test_demo_acceptance.py 5 passed |

**实现要点（与 SPEC 5.3 的对应）**：score 公式按字面实现并随根因输出；第 4 步"祖先闭包内按 mastery 升序+拓扑序取前 3"实现为两段——先做症状过滤（候选若有掌握度 <0.5 的有数据前置，则其失败可被上游解释，降为症状并挂到根因的 `explains`），幸存者按 mastery 升序+拓扑序取前 3。另修复 BKT 小样本 EM 退化：全对/全错序列会把 p_S/p_G 顶到 0.99（"已掌握但总失误"与"未掌握"似然相同后验相反），检测到 p_S/p_G >0.5 即回退默认参数做前向后验。

**demo 诊断真实输出**（`examdiag diagnose --attempts data/demo_attempts.jsonl --concepts data/concepts/ --plan`）：

```
                                 根因诊断报告
┃ # ┃ 根因概念         ┃ 掌握度 ┃ 涉及错题 ┃ 补习路径（按序补）
┃ 1 ┃ 二叉树遍历       │   0.10 │       26 │ 二叉树遍历(ds.tree.traverse)
    │ ds.tree.traverse │        │          │  → 二叉搜索树(ds.bst.bst)
    │                  │        │          │  → AVL平衡旋转(ds.bst.rotate)
    │                  │        │          │  → AVL删除与综合调整(ds.bst.delete)

                               未来 7 天复习计划
┃ Day 1-7 ┃ 二叉树遍历(ds.tree.traverse)   # mastery≈0.10 → interval 1 → 每天
```

（`explains` 含 ds.bst.bst / ds.bst.rotate / ds.bst.delete / ds.forest.traverse / ds.search.btree / ds.tree.threaded——BST 旋转连续错被正确归因为遍历的下游症状。）

```
$ python -m pytest tests/ -q
..........................................................................  [100%]
78 passed in 0.82s
$ ruff check .
All checks passed!
```

依赖变更：networkx、rich 移入主依赖（pyproject）。Wave 1 打 tag `v0.2.0`。

## Wave 2（2026-10-28）：能看 + 能传播

| 任务 | 产出 | 验收 |
|---|---|---|
| 2.1 可视化 | `viz/report.html`（49 KB 单文件，无框架）+ 生成器 `scripts/make_report.py` | 60 节点 SVG 分层布局（最长前置链定层）、mastery 红→黄→绿渐变、点击节点显示涉及错题、根因补习路径加粗；HTML 由真实 diagnose 数据生成 |
| 2.2 GIF | `docs/demo.gif`（59 KB，68 帧 ≈ 5.7 s，1088×642）+ `scripts/make_gif.py`（PIL 逐帧 + ffmpeg palettegen/paletteuse） | 帧内容全部取自真实命令输出：`head -3 data/demo_attempts.jsonl`（输入）→ `examdiag diagnose --attempts ... --plan`（真实子进程 stdout 逐行揭示）；脚本内置断言输出含 `ds.tree.traverse` |
| 2.3 双语 README | `README.md`（英）+ `README.zh-CN.md`（中），第一屏：一句话 → GIF → `pip install -e .` → 示例输出 → 为什么不是错题本 | 两份 README 均无"真题"字样（题库如实描述为 600 道自建题）；`grep -rn 真题 README*.md` 零命中 |
| 2.4 notebook | `examples/demo.ipynb`（+ 生成器 `scripts/make_notebook.py`） | nbclient 实跑通过（cwd=examples/，相对路径 `../data/`），提交的版本**带执行输出**，GitHub 可直接看到结果 |
| 2.5 tag | `v0.3.0` | 推送至 origin |

GIF 渲染细节备忘：Menlo 自带 box-drawing 字形（10px 等宽可无缝拼表格边），只把真 CJK（≥U+2E80）路由给 STHeiti 且字号取 SIZE+4（全角 = 20px = Menlo 两格），与 rich 的"CJK 记 2 格"宽度约定一致，表格边线才能对齐。

硬规则遵守：未修改 `examdiag/` 与 `data/` 下任何文件；`benchmark.md` 未动；README 无"真题"。

```
$ git log --oneline -5   # Wave 2
d69c648 wave2(2.4): examples/demo.ipynb runnable walkthrough (committed with executed outputs)
dadbcd9 wave2(2.3): bilingual README with first-screen structure (gif/install/example/why)
97386e5 wave2(2.2): make_gif.py (PIL frames + ffmpeg palette) -> docs/demo.gif from real diagnose output
c631473 wave2(2.1): single-file viz/report.html (layered SVG, mastery gradient, click-for-wrong-questions) + generator
```

Wave 2 打 tag `v0.3.0`。
