#!/bin/bash
# Wave 0 无人值守执行脚本
# 设计原则：每完成一步 → commit → push 到 GitHub，进度实时同步，失败不中断
cd /Users/xi/Documents/exam-diag || exit 1
source ~/.zshrc >/dev/null 2>&1

LOG=/Users/xi/Documents/exam-diag/run.log
GH=~/.local/bin/gh
# GitHub 账号 noreply 地址：只用于把 commit 认领到账号（贡献图），不是真实收件邮箱
GID=(-c user.name=xi -c user.email=70122327+2422725977@users.noreply.github.com)
P="工作目录 /Users/xi/Documents/exam-diag。先 read SPEC.md 全文了解项目，然后严格执行下面这一项任务，不要跳步、不要顺手做别的任务。"

git branch -M main >> "$LOG" 2>&1

step () {
  local name="$1"; local task="$2"
  echo "" >> "$LOG"
  echo "===== [$name] START $(date '+%F %T') =====" >> "$LOG"
  dsh headless "$P

$task" >> "$LOG" 2>&1
  local rc=$?
  echo "===== [$name] END $(date '+%F %T') exit=$rc =====" >> "$LOG"

  git add -A >> "$LOG" 2>&1
  git "${GID[@]}" commit -q -m "wave0($name): $(date '+%H:%M')" >> "$LOG" 2>&1

  # 每步都推一次；推失败不中断，下一步继续重试
  if git remote get-url origin >/dev/null 2>&1; then
    if git push -q origin main >> "$LOG" 2>&1; then
      echo "PUSHED $(git rev-parse --short HEAD)" >> "$LOG"
    else
      echo "PUSH FAILED at [$name] — 下一步会重试" >> "$LOG"
    fi
  else
    echo "no remote yet, skip push" >> "$LOG"
  fi
  return 0
}

echo "===== WAVE 0 RUN $(date '+%F %T') =====" >> "$LOG"

# ---- 第 0 步：先建仓库，打通后续每一步的增量上传通道 ----
step "bootstrap" "完成 SPEC.md 8.1-8.3 的仓库初始化。这是全部任务的第一步，唯一目的是让后续每一步都能增量上传 GitHub，不要在这里写业务代码。依次执行：1) 按 SPEC 8.1 创建 MIT LICENSE（Copyright (c) 2026 Xin Xia）并 commit；2) 按 SPEC 8.3 写十行以内的极简英文 README.md；3) 确认当前分支是 main（git branch -M main）；4) 用 $GH repo view exam-diag 判断远程是否存在：不存在则执行 $GH repo create exam-diag --public --source=. --remote=origin --push --description 'Find the root-cause concept behind every wrong answer — a knowledge-tracing diagnostic engine for exam mistakes.'，已存在则先 $GH remote add origin git@github.com:2422725977/exam-diag.git 再 git push -u origin main；5) 执行 $GH repo edit --add-topic knowledge-tracing,education,bayesian-knowledge-tracing,spaced-repetition,exam,learning-analytics,python；6) 把 $GH repo view --json name,visibility,url,description 的真实输出和 git remote -v 贴进 PROGRESS.md。若 gh 认证失败或仓库已存在导致冲突，明写原因，不要伪造成功。"

# ---- 引擎优先：先让核心算法跑通 ----
step "skeleton" "完成 SPEC.md Wave 0 的任务 0.1 和 0.2：初始化 Python 包（pyproject.toml、examdiag/__init__.py、pytest/ruff 配置），并实现 examdiag/schema.py 的 Concept/Question/Attempt 三个 pydantic 模型及校验（含 prereqs 环检测）。写 tests/test_schema.py 并跑 pytest 到全绿。把命令与输出追加到 PROGRESS.md。"

step "bkt" "完成 Wave 0 任务 0.5：实现 examdiag/bkt.py，纯 numpy，含 BKT 四参数的前向后验更新与 EM 拟合（推导见 SPEC.md 5.1/5.2）。写单元测试：用真实参数 p_L0=.3,p_T=.1,p_S=.1,p_G=.2 生成 2000 条答题序列，拟合后四参数各自误差必须 < 0.05。跑 pytest 到全绿，把实际拟合出的四个数字贴进 PROGRESS.md。"

step "eval" "完成 Wave 0 任务 0.6：实现 examdiag/eval.py，计算下次作答预测的 AUC 与 RMSE，跑出基线并写入 benchmark.md（表格：model x AUC x RMSE）。用仓库内自造的合成序列（SPEC.md 5.4），不要求联网下载 ASSISTments；尝试联网失败就明写失败原因并改用合成数据。AUC 必须 > 0.65。结果贴进 PROGRESS.md。"

# ---- 知识点：四科各一步，做完一步立刻上传 ----
step "concepts-408" "完成 Wave 0 任务 0.3 的 408 科目部分：生成 data/concepts/408.yaml，恰好 60 个概念节点，覆盖数据结构为主（辅以组成原理/操作系统/网络），每节点字段 id/name/subject/difficulty/prereqs，id 用点分层级如 ds.tree.traverse。必须构成无环 DAG，非根节点至少 1 条入边。写完后用 python 加载校验节点数与环并贴进 PROGRESS.md。"

step "concepts-math1" "完成 Wave 0 任务 0.3 的 math1 科目部分：data/concepts/math1.yaml，恰好 60 个节点，覆盖高等数学/线性代数/概率论与数理统计三块，无环，非根节点有入边。id 前缀分别用 math.calc / math.linalg / math.prob。校验后贴进 PROGRESS.md。"

step "concepts-english" "完成 Wave 0 任务 0.3 的 english 科目部分：data/concepts/english.yaml，恰好 60 个节点，按 SPEC.md 5.2.5 的『能力层级图』设计（词汇层→句法层→篇章层，深度 2-3 层），只有 20-30 条真实依赖边，允许大量节点 prereqs 为空（根节点 <= 40）。校验后贴进 PROGRESS.md。"

step "concepts-politics" "完成 Wave 0 任务 0.3 的 politics 科目部分：data/concepts/politics.yaml，恰好 60 个节点，覆盖马原/毛中特/史纲/思修，其中马原部分必须建全前置边。无环。校验后贴进 PROGRESS.md。"

# ---- 题库：四科各一步 ----
step "questions-408" "完成 Wave 0 任务 0.4 的 408 部分：生成 data/questions/408.jsonl，恰好 150 道题，字段 id/subject/stem/answer/concepts/source，每题 concepts 必须存在于 data/concepts/408.yaml。分批生成（每批 25 道追加写入）。source 用真题格式或 self-built，严禁编造不存在的真题题号。写完后用脚本校验行数=150 且 concept id 全部可解析，结果贴进 PROGRESS.md。"

step "questions-math1" "完成 Wave 0 任务 0.4 的 math1 部分：data/questions/math1.jsonl，恰好 150 道，concepts 必须存在于 data/concepts/math1.yaml，分批追加写入。校验后贴进 PROGRESS.md。"

step "questions-english" "完成 Wave 0 任务 0.4 的 english 部分：data/questions/english.jsonl，150 道（题型含语法/词汇辨析/长难句理解），concepts 必须存在于 data/concepts/english.yaml。若时间紧张可降到 60 道，但必须在 PROGRESS.md 明写实际数量与原因，不许谎报 150。校验后贴进 PROGRESS.md。"

step "questions-politics" "完成 Wave 0 任务 0.4 的 politics 部分：data/questions/politics.jsonl，150 道（单选为主，马原占比不低于 40%），concepts 必须存在于 data/concepts/politics.yaml。若时间紧张可降到 60 道并在 PROGRESS.md 明写实际数量。校验后贴进 PROGRESS.md。"

# ---- 收尾 ----
step "wrapup" "完成 Wave 0 任务 0.7：检查 PROGRESS.md 是否记录了全部任务的真实命令输出与真实数字（缺的补跑补记），确认 pytest 全绿，跑一次 examdiag 包导入自检。在 PROGRESS.md 末尾写『Wave 0 完成情况』小结表：每项任务 / 实际产出数量 / 验收是否通过 / 未完成项与原因。然后 git commit。"

echo "" >> "$LOG"
echo "===== 打版本 tag =====" >> "$LOG"
git "${GID[@]}" tag -a v0.1.0 -m "Wave 0: BKT engine + 4-subject knowledge graph + question bank" >> "$LOG" 2>&1
if git push -q origin v0.1.0 >> "$LOG" 2>&1; then
  echo "TAGGED v0.1.0 PUSHED" >> "$LOG"
else
  echo "tag push failed" >> "$LOG"
fi
echo "===== WAVE 0 ALL DONE $(date '+%F %T') =====" >> "$LOG"
