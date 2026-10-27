# 规格书：论文《Root-Cause Localization on Prerequisite DAGs》

> 交付对象：实现该任务的 AI Agent。本文件是唯一需求来源。
> **最高优先级的约束在第 6 节「反伪造」，违反其中任一条，整篇论文作废。**

## 0. 一句话定位

We study the problem of localizing the minimal set of unmastered concepts that explains a student's observed failures on a prerequisite DAG, and show the problem is NP-hard in general while admitting linear-time solutions on trees, with an FPT algorithm parameterized by treewidth.

## 1. 学术定位（写进 Introduction，不要改口）

**不要声称发明了新算法。** 这个问题在一般图上就是 **Minimum Hitting Set**，NP-hard，已有成熟理论。

真正的贡献点（写论文时必须严格按这个口径）：

1. **结构观察**：前置 DAG 上，每个失败节点 f 的候选解释集是 `H_f = {f} ∪ Anc(f)`，而这族集合具有沿 DAG 的**单调嵌套性**（`u →* v ⇒ H_u ⊆ H_v`），一般 hitting set 实例不具备这个性质。
2. **复杂度下界**：一般 DAG 上仍 NP-hard（从 Set Cover 归约，用两层 DAG 构造）。
3. **可解的特殊情形**：当 G 是树（arborescence）时，RCS 可在 **O(n)** 内最优求解——这是一般 hitting set 没有的。
4. **参数化算法**：以树宽 `tw` 为参数，`O(2^tw · n)` 的 FPT 算法。
5. **近似**：贪心给出 `H(n)` 近似，且在树状实例上达到最优。

一句话：**贡献是"刻画这个特定图结构下问题的可解边界"，不是"发明更快的通用碰集算法"。**

## 2. 形式化定义（LaTeX 里要严格写）

**定义 2.1（前置 DAG）** 有向无环图 `G = (V, E)`，`|V| = n`。边 `(u,v) ∈ E` 表示 u 是 v 的直接前置概念。`Anc(v) = {u : u →* v, u ≠ v}` 为 v 的严格祖先集。`Desc(u)` 为严格后代集。

**定义 2.2（失败观测）** 学生在一批题目上出错，题目到概念的映射给出失败概念集 `F ⊆ V`。

**定义 2.3（解释集 / Root Cause Set）** `R ⊆ V` 是 F 的一个解释集，若
```
∀ f ∈ F:  f ∈ R  ∨  R ∩ Anc(f) ≠ ∅
```
即每个失败概念要么自己就是根因，要么某个未掌握的祖先解释了它。

**定义 2.4（RCS 问题）** 给定 `(G, F)`，求 `|R|` 最小的解释集 `R*`。

**等价的碰集形式（必须有这个引理）**：
```
R* = Minimum Hitting Set over  { H_f = {f} ∪ Anc(f) : f ∈ F }
```

**引理 2.5（单调性）** 若 `u →* v`，则 `H_u ⊆ H_v`，且 `H_u ≠ H_v`（因为 `v ∉ H_u`，`v ∈ H_v`）。
这个引理是后面所有算法的基础，证明不超过五行。

## 3. 要证的定理（三个，不多不少）

**定理 3.1（NP-hardness）** RCS 在一般 DAG 上是 NP-hard。
构造：给定 Set Cover 实例 `(U, S)`，建两层 DAG——第一层为每个 `S_i` 一个节点 `s_i`，第二层为每个 `u_j ∈ U` 一个节点 `u_j`，边 `(s_i, u_j)` 当且仅当 `u_j ∈ S_i`。令 `F = U`。则最小 Set Cover 大小 = 最小解释集大小。归约是双向保持的，要写清两个方向。

**定理 3.2（树上的线性算法）** 若 G 是 arborescence（每个节点入度 ≤ 1），RCS 可在 `O(n)` 求解。
证明思路：自底向上，对每个节点维护"该子树内未覆盖的失败节点数"。若某节点的所有后代失败都已被覆盖则不需选它；否则选它是本轮最优（因为选它能覆盖它的全部后代失败，而不选它就必须在后代里选至少一个，后代的可覆盖集合是它的子集）。关键用引理 2.5 的嵌套性。
**必须写出算法伪码 + 正确性证明 + 复杂度。**

**定理 3.3（FPT）** 以树宽 `tw` 为参数，RCS 可在 `O(2^tw · n)` 时间内最优求解。
用 nice tree decomposition，对每个 bag 维护"bag 内哪些节点被选为根因"的状态，状态数 `2^tw`，转移按 Join/Introduce/Forget 三种节点写清楚。

## 4. 要实现的算法（`paper/code/`）

| 文件 | 内容 | 语言 |
|---|---|---|
| `rcs.py` | `brute_force(G,F)`（指数，仅小图）、`greedy(G,F)`、`tree_linear(G,F)`、`fpt_tw(G,F)` | Python + networkx |
| `generate.py` | 合成 DAG 生成器：随机 DAG（控制 n、边密度、树宽）、树、两层图 | Python |
| `experiments.py` | 跑实验矩阵，结果写 `paper/results/*.json` | Python |
| `baseline.py` | 对比的经典方法：朴素碰集贪心、F 本身作为解（上界） | Python |

**正确性要求**：`brute_force` 与 `tree_linear`、`greedy` 在小图（n ≤ 12）上必须逐个实例比对，结论一致（greedy 允许更差但必须可行）。写 `test_rcs.py`。

## 5. 实验设计（必须真跑，结果进 JSON）

| 实验 | 设置 | 产出 |
|---|---|---|
| E1 正确性 | n ≤ 12 随机 DAG × 200 个实例 | brute_force vs greedy vs tree_linear 的最优解一致率 |
| E2 近似质量 | n ∈ {50,200,500,1000}，F 规模 ∈ {5,10,20} | greedy 解 / 最优解（小 n）/ 理论上界 |
| E3 树的性质 | 随机 arborescence，n ∈ {100,1000,10000} | 运行时间随 n 的曲线，验证线性 |
| E4 FPT | 树宽 ∈ {3,5,8}，n ≤ 200 | 运行时间随 2^tw 的缩放 |
| E5 真实结构 | 用 `exam-diag/data/concepts/*.yaml` 的四科知识图（60 节点/科） | 在真实前置图上的解规模与耗时 |

E5 是这篇论文和真实场景挂钩的地方，必须包含，并说明四科图的实测树宽（用 networkx 的 treewidth 近似算法）。

## 6. 反伪造（最高优先级）

1. **论文里出现的每一个实验数字，都必须能在 `paper/results/*.json` 里 grep 到。** 写一个 `check_paper.py`：正则扫 `paper/main.tex` 里所有数字，逐个核对是否存在于 results 文件；不存在的列出来并以非零退出码失败。
2. **每一条参考文献必须真实存在**：BibTeX 只能由 `fetch_refs.py` 调用 arXiv / Semantic Scholar API 生成，`arxiv_id` 与标题必须能对上。**禁止手写 BibTeX。**
3. **取不到的实验结果就写 `not reported` 或删掉该论断**，不许用"约"、"typically"、"roughly"绕过。
4. 论文里的定理若证明不出来，**降级为 conjecture 并明写**，不许假装证完。

## 7. 论文结构（`paper/main.tex`，英文，arXiv 格式）

用 `article` 类 + `\usepackage{amsmath, amsthm, booktabs, hyperref, algorithm, algpseudocode}`。算法伪码用 `algorithm` + `algpseudocode` 环境（`algorithmic` 语法已过时）。本机 TinyTeX 已装齐这些包，不要引入其他未装包。

| 节 | 内容 | 篇幅 |
|---|---|---|
| Abstract | 问题 + 三个结果（NP-hard / 树上线性 / FPT） | 150 词 |
| 1 Introduction | 动机（教育场景为何要最小解释）、贡献列表 | 0.75 页 |
| 2 Related Work | Model-based diagnosis（Reiter）、Hitting Set、Knowledge Space Theory、Knowledge Tracing | 0.75 页 |
| 3 Problem Definition | 定义 2.1–2.4，引理 2.5 | 1 页 |
| 4 Complexity | 定理 3.1 + 完整归约证明；树情形的结构讨论 | 1 页 |
| 5 Algorithms | 3.2 树线性算法（伪码+证明）、3.3 FPT | 1.5 页 |
| 6 Experiments | E1–E5，表格用 booktabs，图用 pgfplots 或 matplotlib 存 PDF 插入 | 2 页 |
| 7 Discussion & Limitations | 掌握度概率未建模（BKT）是当前局限，作为 future work | 0.5 页 |
| 8 Conclusion | | 0.25 页 |
| References | 20–30 条，全部真引用 | — |

**总长 8–10 页**。正文里每个 `\cite` 必须在 `.bib` 里存在，编译时不能有 undefined reference。

## 8. 中文导读（`paper/zh-guide.md`，必须有）

作者本人看不懂英文论文，所以每节写一段中文白话：

```
## 3 Problem Definition（问题定义）
**这节在说什么**：把"根因定位"翻译成数学语言……
**为什么要这么定义**：因为不定义清楚就没法证明难度……
**你需要能回答**：为什么 H_f 要包含 f 自己？
```

覆盖全部 8 节 + 三个定理，每条 100–200 字。**不许用"如上所述"这类空话糊弄**，要能让人照着讲出来。

## 9. 分波任务

### Wave P0（今晚，5–6 小时）

| # | 任务 | 产出 | 验收 |
|---|---|---|---|
| P0.1 | `paper/fetch_refs.py`：按主题从 arXiv/S2 抓 25–30 篇真论文，生成 `refs.bib` | bib 文件 | 每条有真实 arxiv_id；`grep -c '@'` ≥ 25 |
| P0.2 | `paper/code/rcs.py`：brute_force + greedy + tree_linear | py | `test_rcs.py` 全绿，n≤12 上三者最优值一致 |
| P0.3 | `paper/code/generate.py` + `experiments.py`：跑 E1–E3 | results/*.json | 三个 json 存在，含真实数值 |
| P0.4 | `paper/main.tex` 的骨架 + Abstract + 第 3 节（定义与引理） | tex | `pdflatex` 能编译出 PDF（即使其余节是占位） |
| P0.5 | `paper/check_paper.py`：数字核验脚本 | py | 对当前 tex 跑一遍，能检出人为植入的假数字（自测写进 PROGRESS） |

### Wave P1（第二晚）
- P1.1 定理 3.1 的完整归约证明写进 `paper/main.tex` 第 4 节。
- P1.2 FPT 算法实现 + E4 实验。
- P1.3 E5：读 `exam-diag/data/concepts/*.yaml`（若还没生成就自造四个 60 节点图），跑真实图实验。
- P1.4 编译通过，页数 ≥ 6。

### Wave P2（第三晚）
- P2.1 写第 1、2、5、6、7、8 节正文。
- P2.2 生成实验图表（matplotlib → PDF），插入 tex。
- P2.3 跑 `check_paper.py` 全过。
- P2.4 写 `paper/zh-guide.md` 中文导读。
- P2.5 编译最终 PDF，`check_paper.py` + 编译零 warning。

## 10. 全局约束

- 工作目录 `/Users/xi/Documents/exam-diag/paper/`，随主仓库 push（SSH remote 已配好）。
- 每完成一个任务 `git commit` + `git push`。
- 依赖只允许：numpy、networkx、matplotlib、pytest。
- **LaTeX 环境已就绪**（2026-10 实测）：TinyTeX（TeX Live 2026）装在 `~/Library/TinyTeX`，`pdflatex` / `latexmk` 已软链到 `/opt/homebrew/bin`，`amsmath amsthm booktabs hyperref algorithm algpseudocode` 全部可解析，最小编译测试通过。
- **编译命令统一用**：
  ```bash
  cd paper && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
  ```
  `latexmk` 会自动跑够次数解析 `\ref` 与 `\cite`，不要手写两遍 `pdflatex`。
- 编译后必须检查：PDF 存在、`main.log` 里 `Warning: Reference` 与 `Warning: Citation` 数量为 0。有未定义引用就修，不许留着交付。
- 缺包时用 `tlmgr install <包名>` 补（用户级安装，无需 sudo），并把装了什么记进 PROGRESS.md。
- **不声称投稿**、不发邮件、不联系作者。产出是 preprint 草稿。
- 论文标题页不写导师（没有），作者写 `Xin Xia`，单位写 `Chongqing Technology and Business University`。

## 11. 交付时向用户报告什么

1. PDF 路径与页数
2. 三个定理各是否证完（证完 / 降级为 conjecture）
3. E1–E5 各跑了多少个实例、关键数字
4. `check_paper.py` 的结果
5. 哪些引用抓不到、用什么替代
