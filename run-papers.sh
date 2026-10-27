#!/bin/bash
# 文献矩阵无人值守执行脚本
# 设计：每步 commit + push，失败不中断，进度实时同步
cd /Users/xi/Documents/exam-diag || exit 1
source ~/.zshrc >/dev/null 2>&1

LOG=/Users/xi/Documents/exam-diag/papers/run.log
mkdir -p /Users/xi/Documents/exam-diag/papers
GID=(-c user.name=xi -c user.email=70122327+2422725977@users.noreply.github.com)
P="工作目录 /Users/xi/Documents/exam-diag。先 read SPEC-papers.md 全文了解任务，然后严格执行下面这一项任务，不要跳步、不要顺手做别的任务。"

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
  git "${GID[@]}" commit -q -m "papers($name): $(date '+%H:%M')" >> "$LOG" 2>&1
  if git push -q origin main >> "$LOG" 2>&1; then
    echo "PUSHED $(git rev-parse --short HEAD)" >> "$LOG"
  else
    echo "PUSH FAILED at [$name] — 下一步重试" >> "$LOG"
  fi
  return 0
}

echo "===== PAPERS RUN $(date '+%F %T') =====" >> "$LOG"

step "fetch" "完成 SPEC-papers.md Wave 0 任务 0.1：写 papers/fetch.py，调用 arXiv API 依次执行 SPEC 第 2.1 节的 Q1-Q8 八个检索式，结果按式号分别保存到 papers/raw/Q1.xml ... Q8.xml。硬要求：每次请求之间 sleep 3 秒（arXiv 限速，违反会封 IP）、HTTP 失败重试 3 次、用 stdlib 的 urllib + xml.etree 解析，不引入第三方依赖。跑完后报告每个文件的实际字节数和 opensearch:totalResults 数值，写进 papers/PROGRESS.md。如果某个检索式返回 0 条，明写并调整该检索式的引号写法后重试一次。"

step "parse" "完成 Wave 0 任务 0.2：写 papers/parse.py，读取 papers/raw/*.xml，提取 arxiv_id（去掉 v 后缀）、title、authors、year、venue、direction、abstract，按 arxiv_id 去重（同 id 保留最新版），排除 summary 含 withdrawn/retracted 的条目，输出 papers/papers_raw.csv（UTF-8 无 BOM，字段顺序严格按 SPEC-papers.md 第 3 节）。direction 先按来源检索式初判（Q1/Q2→kt，Q3/Q4→kg，Q5→diag，Q6→llm，Q7→srs，Q8→irt），后续再修正。跑完报告：总行数、去重后行数、重复 id 数（必须为 0），写进 PROGRESS.md。"

step "citations" "完成 Wave 0 任务 0.3：写 papers/enrich.py，读 papers_raw.csv，逐篇调 Semantic Scholar API 补 citation_count、venue、year：https://api.semanticscholar.org/graph/v1/paper/arXiv:<id>?fields=title,citationCount,influentialCitationCount,year,venue 。硬要求：每次请求 sleep 1.1 秒、429 时退避重试 3 次、取不到的填 null（绝对不许填 0）。输出 papers/papers.csv。跑完报告：成功率、null 数量，写进 PROGRESS.md。若中途被限流，记录已处理到第几篇，脚本支持 --resume 从断点继续。"

step "pilot" "完成 Wave 0 任务 0.4：从 papers.csv 里按 relevance 潜在最高的挑 20 篇（优先知识追踪主线的高引用论文），逐篇读摘要，抽取 method、dataset、metric（必须是论文真有的数字，取不到写「未报告」）、limitation（注明是作者原文还是你提炼）、relevance(1-5)，追加写入 papers/extracted.jsonl，每行一个 JSON 对象。禁止一次生成 20 条，分 4 批每批 5 条。跑完在 PROGRESS.md 里贴 20 篇的 arxiv_id 列表和抽取字段的完整率统计。"

step "progress" "完成 Wave 0 任务 0.5：整理 papers/PROGRESS.md，把前面四步的真实命令输出、真实数字、遇到的问题（限流、解析失败、检索式调整）全部记录进去。开头写一段『反伪造三规则』：1) metric 必须来自原文，取不到写未报告；2) 篇数不许凑；3) 抽取失败要明写原因。末尾写 Wave 0 完成情况表。然后确认 papers/ 下所有文件都已 commit。"

echo "" >> "$LOG"
echo "===== PAPERS WAVE 0 DONE $(date '+%F %T') =====" >> "$LOG"
