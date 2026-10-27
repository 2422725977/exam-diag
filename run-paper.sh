#!/bin/bash
# 论文《Root-Cause Localization on Prerequisite DAGs》无人值守执行脚本
# 每步 commit + push，失败不中断
cd /Users/xi/Documents/exam-diag || exit 1
source ~/.zshrc >/dev/null 2>&1

mkdir -p /Users/xi/Documents/exam-diag/paper
LOG=/Users/xi/Documents/exam-diag/paper/run.log
GID=(-c user.name=xi -c user.email=70122327+2422725977@users.noreply.github.com)
P="工作目录 /Users/xi/Documents/exam-diag。先 read SPEC-paper.md 全文了解论文任务，然后严格执行下面这一项任务，不要跳步、不要顺手做别的任务。特别注意 SPEC-paper.md 第 6 节的反伪造约束。"

step () {
  local name="$1"; local task="$2"
  echo "" >> "$LOG"
  echo "===== [$name] START $(date '+%F %T') =====" >> "$LOG"
  dsh headless "$P

$task" >> "$LOG" 2>&1
  local rc=$?
  echo "===== [$name] END $(date '+%F %T') exit=$rc =====" >> "$LOG"
  git add -A >> "$LOG" 2>&1
  git "${GID[@]}" commit -q -m "paper($name): $(date '+%H:%M')" >> "$LOG" 2>&1
  if git push -q origin main >> "$LOG" 2>&1; then
    echo "PUSHED $(git rev-parse --short HEAD)" >> "$LOG"
  else
    echo "PUSH FAILED at [$name] — 下一步重试" >> "$LOG"
  fi
  return 0
}

echo "===== PAPER RUN $(date '+%F %T') =====" >> "$LOG"

step "refs" "完成 SPEC-paper.md Wave P0 任务 P0.1：写 paper/fetch_refs.py，按论文主题从 arXiv API 与 Semantic Scholar 抓 25-30 篇真实论文，生成 paper/refs.bib。主题覆盖四块：model-based diagnosis / hitting set 理论、故障定位 fault localization、Knowledge Space Theory 与前置关系学习、树宽与 FPT 算法。硬要求：BibTeX 只能由脚本从 API 返回的真实元数据生成，绝对禁止手写任何条目；每条必须有真实 arxiv_id；请求间 sleep 3 秒（arXiv）。跑完把 grep -c '@' refs.bib 的真实数字和篇目列表写进 paper/PROGRESS.md。"

step "algo" "完成 Wave P0 任务 P0.2：实现 paper/code/rcs.py，三个函数：brute_force(G,F) 用暴力枚举求最小解释集、greedy(G,F) 用贪心（每轮选覆盖最多未覆盖失败节点的候选，候选集为各 H_f 的并）、tree_linear(G,F) 实现 SPEC 定理 3.2 的自底向上线性算法。再写 paper/code/test_rcs.py：在 n<=12 的随机 DAG 上生成 200 个实例，断言三者返回的集合大小一致（tree_linear 只用于树实例，一般 DAG 上用 greedy 与 brute_force 比）。跑 pytest 到全绿，把真实通过数量和测例数写进 PROGRESS.md。"

step "exp1" "完成 Wave P0 任务 P0.3 的第一部分：写 paper/code/generate.py（随机 DAG 生成器，可控制 n、边密度；arborescence 生成器；两层图生成器）和 paper/code/experiments.py 的 E1、E2 两部分：E1 在 n<=12 上跑 200 实例比对最优性；E2 在 n=50/200/500/1000、|F|=5/10/20 上测贪心解规模与耗时。真实结果写 paper/results/e1.json 与 e2.json。禁止伪造任何数值，跑多慢就记多慢。"

step "exp2" "完成 Wave P0 任务 P0.3 的第二部分：在 experiments.py 里补 E3 实验——随机 arborescence，n=100/1000/10000，测 tree_linear 的运行时间，验证是否近似线性（记录每个 n 的实测耗时）。结果写 paper/results/e3.json，并在 PROGRESS.md 里贴出三个 n 对应的真实秒数。若 n=10000 超过 5 分钟，降到 5000 并明写降级原因。"

step "tex" "完成 Wave P0 任务 P0.4：创建 paper/main.tex（article 类，宏包 amsmath amsthm algorithmic booktabs hyperref），写完整的导言区、标题作者（Xin Xia, Chongqing Technology and Business University）、Abstract，以及第 3 节 Problem Definition（定义 2.1-2.4 + 引理 2.5 及其证明）。其余章节先写 \\section 标题和一句占位（后续 Wave 补）。然后尝试编译：按 SPEC-paper.md 第 10 节的降级链依次试 pdflatex / tectonic，都没有就交付 tex 并写 paper/HOWTO-COMPILE.md。把实际编译方式和结果写进 PROGRESS.md。"

step "checker" "完成 Wave P0 任务 P0.5：写 paper/check_paper.py，功能是正则扫描 paper/main.tex 里所有形如数字（整数、小数、百分比）的 token，逐个到 paper/results/*.json 里核对是否存在；输出未匹配的数字列表，有未匹配则非零退出。自测：临时在 tex 里植入一个明显假的数字（如 0.98765），运行脚本确认能检出，然后删掉植入内容，把自测过程写进 PROGRESS.md。最后跑一次全量 check_paper.py 记录真实输出。"

step "wrap" "整理 paper/PROGRESS.md：把六个步骤的真实命令输出、真实数字、遇到的所有问题（限流、编译失败、超时降级）汇总。开头写『反伪造三规则 + 编译降级说明』。末尾写 Wave P0 完成情况表：每项任务 / 实际产出 / 验收是否通过 / 未完成项与原因。确认 paper/ 下全部文件已 commit。"

echo "" >> "$LOG"
echo "===== PAPER WAVE P0 DONE $(date '+%F %T') =====" >> "$LOG"
