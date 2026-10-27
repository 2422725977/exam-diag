#!/bin/bash
# Wave 0 无人值守执行脚本 —— 串行、每步落盘、失败不中断
cd /Users/xi/Documents/exam-diag || exit 1
source ~/.zshrc >/dev/null 2>&1
LOG=/Users/xi/Documents/exam-diag/run.log
P="工作目录 /Users/xi/Documents/exam-diag。先 read SPEC.md 全文了解项目，然后严格执行下面这一项任务，不要跳步、不要顺手做别的任务。"

step () {
  local name="$1"; local task="$2"
  echo "" >> "$LOG"
  echo "===== [$name] START $(date '+%F %T') =====" >> "$LOG"
  dsh headless "$P

$task" >> "$LOG" 2>&1
  local rc=$?
  echo "===== [$name] END $(date '+%F %T') exit=$rc =====" >> "$LOG"
  git add -A >> "$LOG" 2>&1
  git -c user.name=xi -c user.email=xi@local commit -q -m "wave0: $name" >> "$LOG" 2>&1
  echo "committed: $(git rev-parse --short HEAD 2>/dev/null)" >> "$LOG"
  return 0
}

echo "===== WAVE 0 RUN $(date '+%F %T') =====" >> "$LOG"

step "skeleton" "完成 SPEC.md 第 6 节 Wave 0 的任务 0.1 和 0.2：初始化 Python 包（pyproject.toml、examdiag/__init__.py、pytest/ruff 配置），并实现 examdiag/schema.py 的 Concept/Question/Attempt 三个 pydantic 模型及校验（含 prereqs 环检测）。写 tests/test_schema.py 并跑 pytest 到全绿。把命令与输出追加到 PROGRESS.md。"

step "bkt" "完成 Wave 0 任务 0.5：实现 examdiag/bkt.py，纯 numpy，含 BKT 四参数的前向后验更新与 EM 拟合（推导见 SPEC.md 5.1/5.2）。写单元测试：用真实参数 p_L0=.3,p_T=.1,p_S=.1,p_G=.2 生成 2000 条答题序列，拟合后四参数各自误差必须 < 0.05。跑 pytest 到全绿，把实际拟合出的四个数字贴进 PROGRESS.md。"

step "eval" "完成 Wave 0 任务 0.6：实现 examdiag/eval.py，计算下次作答预测的 AUC 与 RMSE，跑出基线并写入 benchmark.md（表格：model x AUC x RMSE）。数据源优先用仓库内自造的合成序列（SPEC.md 5.4），不要求联网下载 ASSISTments；若尝试联网失败就明写失败原因并改用合成数据。AUC 必须 > 0.65。结果贴进 PROGRESS.md。"

step "concepts-408" "完成 Wave 0 任务 0.3 的 408 科目部分：生成 data/concepts/408.yaml，恰好 60 个概念节点，覆盖数据结构为主（辅以组成原理/操作系统/网络），每节点字段 id/name/subject/difficulty/prereqs，id 用点分层级如 ds.tree.traverse。必须构成无环 DAG，非根节点至少 1 条入边。写完后用 python 加载校验节点数与环并贴进 PROGRESS.md。"

step "concepts-math1" "完成 Wave 0 任务 0.3 的 math1 科目部分：data/concepts/math1.yaml，恰好 60 个节点，覆盖高等数学/线性代数/概率论与数理统计三块，无环，非根节点有入边。id 前缀分别用 math.calc / math.linalg / math.prob。校验后贴进 PROGRESS.md。"

step "concepts-english" "完成 Wave 0 任务 0.3 的 english 科目部分：data/concepts/english.yaml，恰好 60 个节点，按 SPEC.md 5.2.5 的『能力层级图』设计（词汇层→句法层→篇章层，深度 2-3 层），只有 20-30 条真实依赖边，允许大量节点 prereqs 为空（根节点 <= 40）。校验后贴进 PROGRESS.md。"

step "concepts-politics" "完成 Wave 0 任务 0.3 的 politics 科目部分：data/concepts/politics.yaml，恰好 60 个节点，覆盖马原/毛中特/史纲/思修，其中马原部分必须建全前置边。无环。校验后贴进 PROGRESS.md。"

step "questions-408" "完成 Wave 0 任务 0.4 的 408 部分：生成 data/questions/408.jsonl，恰好 150 道题，字段 id/subject/stem/answer/concepts/source，每题 concepts 必须存在于 data/concepts/408.yaml。分批生成（每批 25 道追加写入）。source 用真题格式或 self-built，严禁编造不存在的真题题号。写完后用脚本校验行数=150 且 concept id 全部可解析，结果贴进 PROGRESS.md。"

step "questions-math1" "完成 Wave 0 任务 0.4 的 math1 部分：data/questions/math1.jsonl，恰好 150 道，concepts 必须存在于 data/concepts/math1.yaml，分批追加写入。校验后贴进 PROGRESS.md。"

step "questions-english" "完成 Wave 0 任务 0.4 的 english 部分：data/questions/english.jsonl，150 道（题型含语法/词汇辨析/长难句理解），concepts 必须存在于 data/concepts/english.yaml。若时间紧张可降到 60 道，但必须在 PROGRESS.md 明写实际数量与原因，不许谎报 150。校验后贴进 PROGRESS.md。"

step "questions-politics" "完成 Wave 0 任务 0.4 的 politics 部分：data/questions/politics.jsonl，150 道（单选为主，马原占比不低于 40%），concepts 必须存在于 data/concepts/politics.yaml。若时间紧张可降到 60 道并在 PROGRESS.md 明写实际数量。校验后贴进 PROGRESS.md。"

step "wrapup" "完成 Wave 0 任务 0.7：检查 PROGRESS.md 是否记录了全部 7 项任务的真实命令输出与真实数字（缺的补跑补记），确认 pytest 全绿，跑一次完整的 examdiag 包导入自检。在 PROGRESS.md 末尾写『Wave 0 完成情况』小结表：每项任务 / 实际产出数量 / 验收是否通过 / 未完成项与原因。然后 git commit。"

echo "" >> "$LOG"
echo "===== WAVE 0 ALL DONE $(date '+%F %T') =====" >> "$LOG"
