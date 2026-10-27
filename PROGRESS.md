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
