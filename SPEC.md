# 项目规格书：exam-diag（考研错题根因诊断引擎）

> 交付对象：实现该项目的 AI Agent。本文件是唯一需求来源，按 Wave 顺序执行，每 Wave 结束后必须跑验收命令并把结果写进 `PROGRESS.md`。

## 0. 一句话定位

**Find the root-cause concept behind every wrong answer.**

输入一批错题，输出"你真正缺的前置知识点（3 个以内）+ 按依赖图排序的补习顺序"，而不是再给你一个错题本。

## 1. 为什么做这个（已核实的数据，写进 README 时可用）

2026-10 GitHub 搜索实测：

| 类型 | 代表仓库 | stars |
|---|---|---|
| 真题/笔记资源 | `ddy-ddy/cs-408` 6311、`csseky/cskaoyan` 9324 | 高中位 |
| 刷题应用 | `yd-coder/question408` 39、`lij768423-svg/408-` 30、`6wa1t/408-ai-tutor` 22 | **19–39** |
| 知识追踪工具 | `pykt-team/pykt-toolkit` 452、`CAHLR/pyBKT` 291、`chrispiech/DeepKnowledgeTracing` 313 | 291–452，全部英文研究工具 |

结论：刷题应用同质化严重且全部低位（说明"题库壳子"这条路已死）；知识追踪模型成熟但无中文考试落地。**空位 = 诊断引擎。**

## 2. 反 star 陷阱（实现时必须遵守）

1. 仓库名用英文、通用，不要用 `kaoyan`/`408` 做仓库名（会把用户群锁死）。仓库名 `exam-diag`。
2. `pip install exam-diag` 必须一行能装能跑出结果。
3. README 第一屏（不滚动能看到的区域）必须有：一句话定位 + GIF demo + 安装命令。GIF 用 vhs 或 asciinema 录制，必须有。
4. 不要做登录、不做云同步、不发 star 请求。零配置本地跑。
5. 中英双 README（`README.md` 英文，`README.zh-CN.md` 中文）。

## 3. 架构

```
exam-diag/
├── pyproject.toml
├── README.md                 # 英文
├── README.zh-CN.md
├── docs/
│   ├── METHOD.md             # BKT + 图诊断的数学推导
│   └── DATA_FORMAT.md
├── examdiag/
│   ├── schema.py             # pydantic 模型：Concept / Question / Attempt / ConceptGraph
│   ├── bkt.py                # BKT 四参数，EM 拟合，后验更新
│   ├── graph.py              # DAG 依赖图，拓扑序，上游搜索
│   ├── diagnose.py           # 根因诊断主算法
│   ├── srs.py                # FSRS 式复习调度（按诊断出的短板知识点排）
│   ├── eval.py               # AUC / RMSE 基线评估
│   └── cli.py                # argparse 入口，输出表格 + 可选 JSON
├── data/
│   ├── concepts/             # 按科目分文件，便于分批生成
│   │   ├── 408.yaml          # 60 概念
│   │   ├── math1.yaml        # 60 概念
│   │   ├── english.yaml      # 60 概念
│   │   └── politics.yaml     # 60 概念
│   ├── questions/            # 同上，每科 150 题
│   │   ├── 408.jsonl
│   │   ├── math1.jsonl
│   │   ├── english.jsonl
│   │   └── politics.jsonl
│   └── demo_attempts.jsonl   # 造一份 500 条的答题记录用于 demo
├── tests/                    # pytest，覆盖率 >80%
└── examples/
    └── demo.ipynb
```

## 4. 核心数据结构（`schema.py`）

```python
class Concept(BaseModel):
    id: str                    # 如 "ds.bst.rotate"
    name: str                  # 左旋/右旋
    subject: str               # 408 | math1 | english | politics
    difficulty: float          # 1-5，人工标
    prereqs: list[str]         # 前置概念 id，构成 DAG

class Question(BaseModel):
    id: str
    subject: str
    stem: str                  # 题干文本
    answer: str
    concepts: list[str]        # 本题考察的概念，主概念排第一
    source: str                # 如 "2019-408-真题-33"

class Attempt(BaseModel):
    user_id: str
    question_id: str
    correct: bool
    ts: datetime               # 时间戳，BKT 需要序列顺序
```

约束：`prereqs` 必须无环，`graph.py` 加载时做环检测并报具体环路。

## 5. 数学模型（`docs/METHOD.md` 里要写全推导）

### 5.1 BKT 四参数（每个 concept 独立一套）

- `p_L0`：初始已掌握概率
- `p_T`：每次练习后从未掌握转移到掌握的概率（learn rate）
- `p_S`：掌握了但答错的概率（slip）
- `p_G`：未掌握但蒙对的概率（guess）

后验更新（标准 Bayesian Knowledge Tracing）：

```
P(L_n | correct) = p_Ln(1-p_S) / [p_Ln(1-p_S) + (1-p_Ln)p_G]
P(L_n | wrong)   = p_Ln·p_S   / [p_Ln·p_S   + (1-p_Ln)(1-p_G)]
P(L_{n+1})       = P(L_n|obs) + (1 - P(L_n|obs))·p_T
```

### 5.2 EM 拟合

- E 步：按当前参数前向算每个时刻的 `P(L_n)` 与后验，得"该时刻处于已掌握状态"的责任度 `γ_n`。
- M 步：闭式重估 `p_S = Σ(1-γ_n)·x_n / Σ(1-γ_n)`、`p_G = Σγ_n·(1-x_n)/Σγ_n`，`p_T` 用相邻 γ 的期望转移率，`p_L0` 取首时刻 γ 均值。
- 迭代至 log-likelihood 相对变化 < 1e-6 或 200 轮。四参数各加 `[0.01, 0.99]` 截断。
- 可用 `pyBKT` 做交叉验证比对，但主实现必须自写（软著需要自有源码）。

### 5.2.5 四科的图结构差异（实现时必须区分，不要一套参数硬套）

| 科目 | 图规模 | 深度 | 边密度 | 特点与处理 |
|---|---|---|---|---|
| `408` | 60 节点 | 4–5 层 | 密 | 严格前置：`栈`→`递归`→`树遍历`→`BST 旋转`。DAG 最规范，诊断效果最好 |
| `math1` | 60 节点 | 4 层 | 中密 | 高数→线代→概率三块之间有弱耦合（如"极限"→"导数"→"级数"）。跨块边要人工确认，别乱连 |
| `english` | 60 节点 | 2–3 层 | 稀疏 | 本质是**能力层级图**而非严格 DAG：词汇层→句法层→篇章层。只有 20–30 条真依赖边（如 时态→完成时→虚拟语气），其余节点无入边，允许 `prereqs: []` |
| `politics` | 60 节点 | 3–4 层 | 密 | 马原概念链最强（唯物论→辩证法→认识论→历史唯物主义），史纲按时间线性，思修较松。马原部分必须建全边 |

`graph.py` 的环检测对四科都要跑，但**只对 `408`/`math1`/`politics` 强制要求非根节点有入边**；`english` 允许孤立节点（根节点数 ≤ 40 即合格）。

### 5.3 根因诊断算法（`diagnose.py`）

```
输入：某用户全部 Attempt，概念 DAG G
1. 对每个概念 c 跑 BKT 拟合 → mastery[c] ∈ [0,1]
2. 找错题集合 W 的概念集合 C_w
3. 对每个 c ∈ C_w：
   score(c) = (1 - mastery[c]) * Π_{a ∈ ancestors(c)} (1 - mastery[a])^(1/d(a,c))
   其中 d(a,c) 是图上距离，指数项让"远但同样未掌握的前置"权重衰减
4. 在 G 上取 C_w 的祖先闭包子图，按 mastery 升序 + 拓扑序，取前 3 个作为根因输出
5. 对每个根因给出一条补习路径：从该根因到目标概念的最短路径上的概念序列
输出：根因列表（含 mastery、图距离、涉及错题数）+ 补习路径
```

必须处理的边界：某概念 attempt 数 < 3 时不输出（避免小样本乱判），标记为 `insufficient_data`。

### 5.4 评估（`eval.py`）

- 公开基线：ASSISTments 2012 数据集（`https://sites.google.com/site/assistmentsdata/`，若下载失败用仓库内 `data/demo_attempts.jsonl` 自造数据并在 README 注明）。
- 指标：下次作答预测 **AUC**、**RMSE**。要求自写 BKT 的 AUC 与 pyBKT 差距 < 0.02。
- 输出 `benchmark.md` 表：model × AUC × RMSE。

## 6. 分波次任务（按顺序喂给 Agent，每波一次会话）

### Wave 0 —— 今晚跑（目标：能跑的引擎 + 四科数据 + 基线数字）

**时间预算（按 6 小时窗口排，共 360 分钟）**：

| 阶段 | 任务 | 预算 | 累计 |
|---|---|---|---|
| A | 0.1 + 0.2 骨架与 schema | 25 min | 25 |
| B | 0.5 `bkt.py` + 单元测试（含合成数据拟合） | 60 min | 85 |
| C | 0.6 `eval.py` + 基线数字 | 25 min | 110 |
| D | 0.3 四科知识点 240 个 | 75 min | 185 |
| E | 0.4 四科题目 600 道 | 145 min | 330 |
| F | 0.7 PROGRESS + commit | 20 min | 350 |

**先做 B/C 再做 D/E**：引擎先通，数据后补。这样即使数据标注超时，你拿到的是"能跑的引擎 + 少量数据"，而不是"600 道题但跑不起来"。

| # | 任务 | 产出 | 验收 |
|---|---|---|---|
| 0.1 | 初始化仓库、pyproject、pytest、ruff | 可 `pip install -e .` | `python -c "import examdiag"` 无报错 |
| 0.2 | 写 `schema.py` 三类模型 + 校验器 | 含 prereq 环检测 | `pytest tests/test_schema.py` 全绿 |
| 0.3 | **精标知识点 240 个**（4 科 × 60），拆 4 个文件 | `data/concepts/{科目}.yaml` | 四科各恰好 60 节点；408/math1/politics 无环且非根节点有入边；english 根节点 ≤40；跨文件 id 唯一 |
| 0.4 | **精标题目 600 道**（4 科 × 150），拆 4 个文件 | `data/questions/{科目}.jsonl` | 每题 ≥1 个 concept 且 id 存在于对应科目 concepts；每科恰好 150 行；无重复 id |
| 0.5 | 写 `bkt.py`：前向后验 + EM 拟合 | 纯 numpy 实现 | 合成数据（p_L0=.3,p_T=.1,p_S=.1,p_G=.2，2000 条序列）拟合，四参数误差 < 0.05 |
| 0.6 | 写 `eval.py` 跑 AUC/RMSE | `benchmark.md` | 合成数据 AUC > 0.65；结果写进文件 |
| 0.7 | `PROGRESS.md` 记录全部验收输出 + `git commit` | — | 含实际命令与实际数字，不许写"预计" |
| 0.8 | **建远程仓库并 push**（见 8.1） | GitHub public 仓库 + LICENSE | `gh repo view --json name,visibility,url` 返回 public；本地与远程 commit 一致 |

**D/E 是纯 LLM 标注工作量，占 4 小时。硬规则：**

- 每科标注完成后**立刻落盘并 commit**（`wave0: concepts <科目> 60 done`），不许四科都做完再一起写。
- 单次生成限制在 20–30 条/批，追加写入，避免长上下文导致后段质量崩塌。
- 600 道题若 6 小时内到不了，**按科目优先级降级**：先保 `408` 和 `math1` 各 150 道，`english`/`politics` 降到 60 道并在 `PROGRESS.md` 写明实际数量和剩余待补。绝不编造"已完成"。
- 每题必须有真实出处（`source` 字段：真题年份题号或自编标 `self-built`），禁止编造不存在的真题题号。

### Wave 1 —— 第二晚（目标：诊断能力）

1.1 `graph.py`：networkx 建 DAG，拓扑排序、祖先闭包、最短路径、环检测。
1.2 `diagnose.py`：实现第 5.3 节算法，含 `insufficient_data` 边界。
1.3 `srs.py`：按根因掌握度排序，给出未来 7 天每天该复习的概念序列（间隔重复，间隔按 mastery 反比）。
1.4 `cli.py`：`examdiag diagnose --attempts demo_attempts.jsonl --concepts concepts.zh.yaml` 输出彩色表格：根因 / 掌握度 / 涉及错题数 / 补习路径。
1.5 造 `demo_attempts.jsonl`：500 条，人为植入"BST 旋转变形题连续错 + 其前置『二叉树遍历』也错"的模式，验证引擎能诊断出这个根因。
1.6 测试：断言 demo 数据上诊断结果 = `["ds.tree.traverse", ...]`。

**验收**：`examdiag diagnose` 在 demo 数据上输出的第 1 个根因必须是 `ds.tree.traverse`。

### Wave 2 —— 第三晚（目标：能看 + 能传播）

2.1 单文件 HTML 可视化 `viz/report.html`（不用前端框架，D3 走 CDN）：知识依赖图力导向布局，节点颜色按 mastery 从红到绿渐变，点击节点显示该概念涉及的错题数与补习路径。数据由 `examdiag.cli diagnose --json` 导出后内联进 HTML，双击即可在浏览器打开。
2.2 **GIF 录制方案（本机无 vhs/asciinema，不要尝试安装）**：写 `scripts/make_gif.py`，用 PIL 逐帧渲染终端风格的画面（等宽字体画黑底绿字的诊断输出，逐行淡入），再用已安装的 `ffmpeg` 合成为 `docs/demo.gif`，控制在 800×500、12fps、15 秒、≤2MB。要展示的核心时序：输入命令 → 表格逐行出现 → 高亮第一行根因。
2.3 写英文 `README.md` + 中文 `README.zh-CN.md`。第一屏（不滚动可见）必须是：**一句话定位 → GIF → `pip install -e .` → 3 行示例命令 → 为什么不是错题本**。**必须诚实标注**：题库为 600 道自建题（不是真题）、benchmark 基于合成序列。禁止出现"考研真题库"字样。
2.4 `examples/demo.ipynb` 可一键运行，输出诊断结果表格。
2.5 打 tag `v0.3.0` 并推送（v0.1.0/v0.2.0 已被占用），不发布 PyPI。

### Wave 3 —— 第四晚（目标：论文素材 + 软著）

3.1 `docs/METHOD.md` 补全第 5 节推导 + 图示。
3.2 论文草稿 `paper/draft.md`：标题候选、Abstract、Related Work（引 pyBKT / DKT / GKT 三篇即可）、方法、实验、局限。目标定位 arXiv preprint + 教学类 workshop，**不投顶会**。
3.3 软著材料：从源码抽 60 页（前 30 页 + 后 30 页，每页 ~50 行）+ 软件说明书 30 页（功能、运行环境、操作流程）。放 `docs/copyright/`。

## 7. 全局约束（给 Agent 的硬规则）

- Python ≥ 3.10，依赖只用 numpy / pydantic / networkx / pytest / rich / pyyaml。**不引入 scikit-learn 做 BKT**（要自写，软著要自有源码）。
- 所有中文文本字段用 UTF-8，不加 BOM。
- 每个 Wave 结束必须 `git commit`，commit message 格式 `wave0: <做了什么>`。
- 不许在验收未通过时标记完成。`PROGRESS.md` 里贴真实命令输出。
- 每波预计 4–8 小时，Wave 0 若超时，优先保 0.5/0.6（引擎 + 基线），题库标注可降到 200 道并在 PROGRESS 里写明实际数量。

## 8. GitHub 上传与发布

### 8.1 Wave 0 一跑完就上传（任务 0.8）

仓库必须 **public**。私有仓库搜不到，也涨不了 star。

`gh` 已登录账号 `2422725977`（token scopes 含 `repo`），路径 `~/.local/bin/gh`。

**commit 身份**：用 GitHub 分配的 noreply 地址，不是真实邮箱——

```bash
git config user.name xi
git config user.email "70122327+2422725977@users.noreply.github.com"
```

这个地址由账号 ID（70122327）和 login 拼成，邮件发进去收不到，作用只是让 GitHub 把 commit 认领到你的账号上。不做这步，所有提交在 profile 贡献图里都是一片空白。

```bash
cd ~/Documents/exam-diag
git branch -M main

cat > LICENSE <<'EOF'
MIT License

Copyright (c) 2026 Xin Xia

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

git add LICENSE && git commit -m "chore: MIT license"

gh repo create exam-diag --public --source=. --remote=origin --push \
  --description "Find the root-cause concept behind every wrong answer — a knowledge-tracing diagnostic engine for exam mistakes."
```

### 8.2 About 区配置（直接决定能不能被搜到）

```bash
gh repo edit --add-topic knowledge-tracing,education,bayesian-knowledge-tracing,spaced-repetition,exam,learning-analytics,python
```

About 区三项都要填满：**Description**（上面那句）、**Topics**（上面那串）、**Website**（有 demo 页就填，没有可以留空）。Topics 是 GitHub 搜索的主要召回来源，不填等于放弃一半自然流量。

### 8.3 Wave 0 结束必须补一个极简 README

刚 push 的仓库没有 README，路人点进来看到裸代码会直接关掉。所以 8.1 之后**立刻**写一个 10 行的英文 README（不等 Wave 2 的完整版）：

```markdown
# exam-diag

Find the **root-cause concept** behind every wrong answer — not another mistake notebook.

[one GIF here later]

## Install
pip install -e .

## Use
examdiag diagnose --attempts data/demo_attempts.jsonl --concepts data/concepts/
```

验收：`gh repo view --json name,visibility,url,description` 返回 `"visibility":"PUBLIC"` 且 description 非空；浏览器打开仓库 URL 第一屏能看到那句话。

### 8.4 社区发布（人工做，Agent 不碰）

- 小红书 / 知乎 / B站：中文标题"我把考研错题做成了诊断报告"
- Hacker News / r/learnmachinelearning：英文标题 "I built a root-cause diagnostic engine for exam mistakes"
- 发布时机：开学前 2 周、考研报名期（10 月）、出分后（2 月）
- 绝不买 star、绝不 star4star（违反 GitHub ToS，会被封号）

### 8.5 增量上传：每完成一个任务就 push 一次

不要憋到最后一次性推。正确节奏是 **每完成一个任务 → commit → push**：知识点标完一科推一次，题库做完一科推一次。三个理由：

1. 6 小时的产出随时有异地备份，本机出事不丢；
2. GitHub 上 commit 时间线连续，路人点进来看提交记录会判断"这项目在活着"；
3. 做到一半被打断，第二天从最后一个 commit 接着来，不用重跑。

Wave 1/2/3 沿用同一节奏，每波结束打一个 tag（`v0.2.0`、`v0.3.0`…），让版本可回溯。
