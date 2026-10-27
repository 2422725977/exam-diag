# Data Format

exam-diag 的三类专业文件：知识点图谱（YAML）、题库（JSONL）、作答记录（JSONL）。
全部 UTF-8（无 BOM）。schema 由 `examdiag/schema.py` 的 pydantic 模型强校验。

## 知识点图谱 `data/concepts/<subject>.yaml`

```yaml
subject: "408"          # 408 | math1 | english | politics
concepts:
  - {id: ds.bst.rotate, name: AVL平衡旋转, subject: "408", difficulty: 5, prereqs: [ds.bst.bst]}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | 点分层级 id（`^[a-z][a-z0-9]*(\.[a-z0-9_-]+)+$`），跨文件唯一 |
| `name` | str | 中文概念名 |
| `subject` | str | 四科之一（YAML 中未加引号的 `408` 会被解析成 int，加载器自动拉回字符串） |
| `difficulty` | float | 1–5，人工标注 |
| `prereqs` | list[str] | 前置概念 id；构成 DAG，加载时做未知引用与环检测（报具体环路） |

科目差异（SPEC 5.2.5）：`408`/`math1`/`politics` 是严格前置 DAG（非根节点都有入边）；
`english` 是能力层级图（词汇→句法→篇章），大量节点 `prereqs: []`（根节点 ≤ 40）。

校验：`python scripts/validate_data.py concepts data/concepts/408.yaml --subject 408`

## 题库 `data/questions/<subject>.jsonl`

每行一个 JSON 对象（`.jsonl`，中文原文不转义）：

```json
{"id": "q408-001", "subject": "408", "stem": "题干…\nA. …\nB. …\nC. …\nD. …", "answer": "A", "concepts": ["ds.tree.traverse"], "source": "self-built"}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | `q<subject>-NNN`，每科内连续无重复 |
| `stem` | str | 完整题干（含选项，`\n` 分隔） |
| `answer` | str | 正确答案（选择题为选项字母） |
| `concepts` | list[str] | 本题考察概念，**主概念排第一**；≥1 个且必须存在于对应科目图谱 |
| `source` | str | 真实出处；自编题一律 `self-built`，严禁编造真题题号 |

校验：`python scripts/validate_data.py questions data/questions/408.jsonl --subject 408 --concepts data/concepts/408.yaml`

## 作答记录 `data/demo_attempts.jsonl`（Wave 1 落地）

```json
{"user_id": "demo-user", "question_id": "q408-013", "correct": false, "ts": "2026-10-28T09:05:00"}
```

BKT 按 `ts` 排序消费序列；`question_id` 必须能在题库中解析到概念。
