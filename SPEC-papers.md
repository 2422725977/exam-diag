# 规格书：exam-diag 文献矩阵（papers/）

> 交付对象：实现该任务的 AI Agent。本文件是唯一需求来源，按 Wave 顺序执行，每 Wave 结束必须跑验收命令并把真实输出写进 `papers/PROGRESS.md`。

## 0. 一句话定位

为 `exam-diag`（考研错题根因诊断引擎）建立可复用的文献地基：把知识追踪、概念依赖、错误归因三个方向的论文结构化成一张可检索、可对比、可引用的矩阵，直接产出论文的 Related Work。

## 1. 为什么做这个

`exam-diag` 的技术路线是「BKT 掌握度估计 + 知识依赖图上的根因回溯」。这条路线的三个支柱方向在 arXiv 上的真实体量（2026-10 实测 `opensearch:totalResults`）：

| 检索式 | 命中 |
|---|---|
| `all:"knowledge tracing"` | 298 |
| `cat:cs.CY AND all:"knowledge+tracing"` | 120 |
| `all:"knowledge graph" AND all:"education"` | 112 |
| `all:"large language model" AND all:"tutoring"` | 397 |
| `all:"spaced repetition"` | 21 |
| `all:"misconception" AND all:"diagnosis"` | 12 |
| `all:"concept prerequisite"` | **6** |

**必须写进产出的重要限定**：`concept prerequisite` 仅 6 篇、`misconception diagnosis` 仅 12 篇，不代表该方向无人研究，而是因为教育数据挖掘的主战场在 **EDM / KDD / ACL / NeurIPS** 会议，arXiv 覆盖不全。矩阵里必须有一节列出这个盲区，防止后续把「arXiv 上没有」误判成「世上没有」。

## 2. 抓取范围（硬约束）

### 2.1 检索式（按顺序查询，结果合并去重）

| # | search_query | 抓取上限 | 排序 | 用途 |
|---|---|---|---|---|
| Q1 | `all:"knowledge tracing"` | 100 | relevance | 核心 |
| Q2 | `cat:cs.CY AND all:"knowledge tracing"` | 40 | relevance | 应用侧补充 |
| Q3 | `all:"knowledge graph" AND all:"education"` | 60 | relevance | 图谱建法 |
| Q4 | `all:"concept prerequisite" OR all:"prerequisite relation"` | 全部（约 20） | relevance | 空白区 |
| Q5 | `all:"misconception detection" OR all:"misconception diagnosis" OR all:"error diagnosis" AND all:"learning"` | 全部（约 30） | relevance | 根因归因 |
| Q6 | `all:"large language model" AND all:"tutoring"` | 60 | submittedDate | LLM 新方向 |
| Q7 | `all:"spaced repetition" OR all:"memory model" AND all:"learning"` | 全部（约 30） | relevance | 调度算法 |
| Q8 | `all:"item response theory" AND all:"neural"` | 30 | relevance | 测评基线 |

**时间范围**：`submittedDate` 在 2014-01-01 之后（2015 年 DKT 是深度学习 KT 的起点，更早的 BKT 经典只通过引用补）。Q6 不限年份但只取 2023 后。

### 2.2 去重与筛选

- 按 arXiv ID 去重（同一篇的 v1/v2/v3 只保留最新版，DOI 相同也合并）。
- 排除 `<summary>` 含 "withdrawn" / "retracted" 的条目。
- **保留** 3–5 篇高引综述（survey/review），它们不参与方法对比表，单独列。
- 目标最终规模：**180–260 篇**。低于 150 说明检索式漏了，回头放宽 Q4/Q5；高于 300 说明筛得不严，收紧到 citationCount ≥ 5 或相关性排前。

### 2.3 影响力补全

arXiv 不给引用数。对每篇用 Semantic Scholar 补：

```
https://api.semanticscholar.org/graph/v1/paper/arXiv:<id>?fields=title,citationCount,influentialCitationCount,year,venue,abstract
```

- 限速 **1 req/秒**，必须 sleep，否则 429。
- 取不到的（无 S2 记录）标记 `citationCount: null`，**不许填 0**——0 和 null 是两回事，前者会污染排序。

## 3. 数据结构

`papers/papers.csv`，UTF-8 无 BOM，表头固定：

| 字段 | 说明 |
|---|---|
| `arxiv_id` | 不带 v 后缀，如 `2402.03300` |
| `title` | 原文标题，不改写 |
| `authors` | 分号分隔，姓在前 |
| `year` | 发表年 |
| `venue` | 会议/期刊名，arXiv 未标注则写 `arXiv` |
| `citation_count` | 整数或空 |
| `direction` | `kt` 知识追踪 / `kg` 图与前置 / `diag` 错误归因 / `llm` 大模型 / `srs` 记忆调度 / `irt` 测评 |
| `method` | 一句话方法名，如 `BKT`、`DKT`、`DKVMN`、`SAKT` |
| `dataset` | 数据集名，多个分号分隔；无实验则空 |
| `metric` | 指标名 + 数值，如 `AUC=0.82`；无则空 |
| `limitation` | 作者自述局限或你提炼的一句（须标注来源：`作者原文` / `提炼`） |
| `relevance` | 1–5，与「根因诊断」的相关度，3 以下不进矩阵 |
| `abstract` | 摘要全文 |

## 4. 产出物（四个文件，缺一不可）

### 4.1 `papers/papers.csv`
上述全表，行数 = 去重后实际篇数。

### 4.2 `papers/matrix.md`
方法对比表，只收 `relevance ≥ 3` 的：

| Method | Year | Venue | Direction | Dataset | Metric | Key idea（一句） | Limitation |

要求：
- 同一 Method 的多个变体合并成一行，在 Key idea 里注明变体。
- Metric 列必须是**论文里真有的数字**，没有就写 `未报告`，禁止估算。
- 按 Direction 分节，每节内按 Year 升序。

### 4.3 `papers/roadmap.md`
- **时间线**：2015 DKT → 2019 SAKT → 2020 AKT → 2021 GKT → 近年 LLM-KT，每代一句话说清解决了上一代的什么。
- **空白区**：明确列出 2–3 个候选创新点，每条给出「谁做过」「做到什么程度」「你没被占的位置」。这是这份矩阵最有价值的部分。
- **arXiv 覆盖盲区**：按第 1 节写清 EDM/KDD/ACL 的缺口，并列出 5 个值得手工补的会议/期刊。

### 4.4 `papers/references.bib`
每个 `relevance ≥ 3` 的条目一条 BibTeX，key 格式 `<第一作者姓><年份>_<arxiv_id去点>`。

## 5. 分波任务

### Wave 0（今晚，4–6 小时）

| # | 任务 | 产出 | 验收命令 |
|---|---|---|---|
| 0.1 | 写 `papers/fetch.py`：调 arXiv API，8 个检索式循环，含 3 秒限速、重试、XML 解析 | `papers/raw/*.xml` + `fetch.py` | 8 个文件都存在，每个 XML 含 `totalResults` |
| 0.2 | 解析 + 去重，输出 `papers/papers_raw.csv` | csv | `wc -l` ≥ 150；重复 arxiv_id = 0 |
| 0.3 | Semantic Scholar 补 citationCount，限速 1/秒，失败重试 3 次 | 同上 csv 补字段 | 有 citation_count 的行 ≥ 80%；缺失的是 null 不是 0 |
| 0.4 | 试跑 20 篇：人工级抽取 method/dataset/metric/direction/relevance | 20 行完整 | 抽查 5 篇与原文一致，写进 PROGRESS.md |
| 0.5 | `papers/PROGRESS.md` 记录所有真实输出 | — | 含实际行数、实际耗时 |

### Wave 1（第二晚）

- 1.1 按 direction 分批抽取全部论文（每批 25 篇追加写入），禁止一次生成几百行。
- 1.2 生成 `matrix.md`（只收 relevance ≥ 3）。
- 1.3 生成 `references.bib`。
- 1.4 验收：`matrix.md` 行数 = relevance≥3 的篇数；随机抽 10 行回原文核对 metric 数值。

### Wave 2（第三晚）

- 2.1 写 `roadmap.md`：时间线 + 空白区 + 覆盖盲区。
- 2.2 写 `papers/README.md`：一句话说明这份矩阵是什么、怎么用、更新日期。
- 2.3 commit + push。

## 6. 反伪造（三条硬规则，写进 PROGRESS.md 开头）

1. **metric 数值必须来自论文原文**，取不到写 `未报告`。禁止用「约」「~」或估算值。
2. **篇数不许凑**。实际 173 篇就写 173，不许写 180。
3. **抽取失败要明写**：哪些论文的 dataset/metric 字段为空、为什么为空（无实验 / 付费墙 / 解析失败）。

## 7. 全局约束

- 工作目录 `/Users/xi/Documents/exam-diag/papers/`，这是 exam-diag 仓库的子目录，随主仓库一起 push。
- 每完成一个任务 `git commit` + `git push`（remote 已配好 SSH，见主 SPEC 8.5）。
- arXiv 限速 1 req/3 秒，Semantic Scholar 1 req/秒；**违反会封 IP**，把 sleep 写死在代码里。
- 不下载 PDF（体积大、无必要），只用 API 的 abstract。需要读全文时单独处理。

## 8. 不做的事

- 不写综述正文（那是 Wave 3 之后、你自己动笔的事）。
- 不投任何会议、不发邮件联系作者。
- 不追求覆盖所有会议论文——这份矩阵的定位是「arXiv 可检索部分 + 明确标注盲区」。
