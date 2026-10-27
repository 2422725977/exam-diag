# exam-diag

Find the **root-cause concept** behind every wrong answer — not another mistake notebook.

Give it a list of wrong answers, get back the 3 upstream concepts you actually failed to learn,
ordered by the dependency graph so you know what to study first.

## Install

```bash
pip install -e .
```

## Use

```bash
examdiag diagnose --attempts data/demo_attempts.jsonl --concepts data/concepts/
```

## Status

Wave 0 in progress: BKT engine + 4-subject knowledge graph (408 / math / english / politics).
