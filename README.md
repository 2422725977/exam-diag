# exam-diag

Find the **root-cause concept** behind every wrong answer — not another mistake notebook.

![demo](docs/demo.gif)

## Install

```bash
pip install -e .
```

## Use

```bash
# which upstream concepts should you actually re-learn? (+ 7-day review plan)
examdiag diagnose --attempts data/demo_attempts.jsonl --concepts data/concepts/ --plan

# JSON output for scripts
examdiag diagnose --attempts data/demo_attempts.jsonl --concepts data/concepts/ --json
```

On the bundled demo data the engine reports:

```
┃ 1 │ 二叉树遍历 ds.tree.traverse │ mastery 0.10 │ 26 wrong │
    remedy: 二叉树遍历 → 二叉搜索树 → AVL平衡旋转 → AVL删除
```

…i.e. the BST-rotation mistakes were really a **tree-traversal** gap.

## Why not another mistake notebook

A mistake notebook collects *what* you got wrong. exam-diag tells you *why*:

1. every attempt is attributed to the concepts its question tests;
2. a Bayesian Knowledge Tracing model (forward posterior + EM, pure numpy) is
   fitted per concept → a mastery probability;
3. wrong answers are walked **up the prerequisite graph** — a failed topic whose
   prerequisites are also weak is a symptom; the topmost broken concept is the
   root cause;
4. each root cause comes with a remedy path and a 7-day spaced-repetition plan
   (interval inversely proportional to mastery).

## What's inside

- `examdiag/` — BKT engine, DAG operations, diagnosis, scheduler, CLI
- `data/concepts/` — 4-subject knowledge graph, 240 concepts (408 / math1 / english / politics)
- `data/questions/` — 600 self-built multiple-choice questions used for demos and tests
- `benchmark.md` — next-response prediction benchmark (self-written BKT AUC 0.79 on synthetic data)
- `viz/report.html` — single-file visualization of the demo diagnosis (open it in a browser)
- `examples/demo.ipynb` — runnable notebook walkthrough

Formats are documented in [docs/DATA_FORMAT.md](docs/DATA_FORMAT.md). No login,
no cloud, zero config — everything runs locally. MIT licensed.

中文说明见 [README.zh-CN.md](README.zh-CN.md)。
