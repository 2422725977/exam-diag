#!/bin/bash
# exam-diag 全波次执行脚本（Wave 2 → Wave 6）
# 特性：按 tag 断点续跑，已完成的波次自动跳过；每步 commit + push；闸门失败即停
cd /Users/xi/Documents/exam-diag || exit 1
source ~/.zshrc >/dev/null 2>&1

LOG=/Users/xi/Documents/exam-diag/run-all.log
GID=(-c user.name=xi -c user.email=70122327+2422725977@users.noreply.github.com)
P="工作目录 /Users/xi/Documents/exam-diag。先 read SPEC.md 中对应的 Wave 章节，然后严格执行下面这一项任务，不要跳步、不要顺手做别的任务。"

has_tag () { git rev-parse -q --verify "refs/tags/$1" >/dev/null 2>&1; }

step () {
  local name="$1"; local task="$2"
  [ -f STOP ] && { echo "===== [$name] SKIPPED (STOP gate) =====" >> "$LOG"; return 0; }
  echo "" >> "$LOG"
  echo "===== [$name] START $(date '+%F %T') =====" >> "$LOG"
  dsh headless "$P

$task" >> "$LOG" 2>&1
  echo "===== [$name] END $(date '+%F %T') exit=$? =====" >> "$LOG"
  git add -A >> "$LOG" 2>&1
  git "${GID[@]}" commit -q -m "$name: $(date '+%m-%d %H:%M')" >> "$LOG" 2>&1
  git push -q origin main >> "$LOG" 2>&1 \
    && echo "PUSHED $(git rev-parse --short HEAD)" >> "$LOG" \
    || echo "PUSH FAILED at [$name]" >> "$LOG"
  return 0
}

tag_wave () {
  [ -f STOP ] && { echo "TAG $1 SKIPPED (STOP gate active)" >> "$LOG"; return 0; }
  git "${GID[@]}" tag -a "$1" -m "$2" >> "$LOG" 2>&1
  git push -q origin "$1" >> "$LOG" 2>&1 && echo "TAGGED $1" >> "$LOG" || echo "tag $1 push failed" >> "$LOG"
}

echo "" >> "$LOG"; echo "===== RUN-ALL $(date '+%F %T') =====" >> "$LOG"

# ============ WAVE 2：能看 + 能传播 ============
if has_tag v0.3.0; then echo "skip wave2" >> "$LOG"; else
step "w2-viz" "完成 SPEC Wave 2 的 2.1：创建 viz/report.html，单文件 HTML 可视化。用 examdiag.cli diagnose --json 导出的数据内联进页面（不许页面内 fetch 本地文件，必须双击可开）。用 D3 v7 CDN 做力导向布局展示知识依赖图，节点颜色按 mastery 从红(0)→黄(0.5)→绿(1) 渐变，节点大小按涉及错题数缩放，点击节点侧栏显示该概念的 error 列表与补习路径。用 data/demo_attempts.jsonl + data/concepts 的真实诊断结果生成，不许手写假数据。"

step "w2-gif" "完成 SPEC Wave 2 的 2.2：写 scripts/make_gif.py，用 PIL 逐帧渲染黑底终端风格画面（等宽字体，逐行淡入效果），再用 ffmpeg 合成 docs/demo.gif。规格：800×500、12fps、15 秒、≤2MB。内容必须真实取自 examdiag.cli diagnose 的实际输出（先跑命令抓 stdout，再渲染）。核心时序：输入命令 → 表格逐行出现 → 第一行根因高亮闪烁两次。跑完报告 GIF 实际文件大小。"

step "w2-readme" "完成 SPEC Wave 2 的 2.3：重写 README.md（英文）与 README.zh-CN.md（中文）。第一屏不滚动必须依次看到：一句话定位（Find the root-cause concept behind every wrong answer — not another mistake notebook.）→ docs/demo.gif → pip install -e . → 3 行示例命令 → 为什么不是错题本（3 条 bullet）。硬约束：禁止出现『考研真题库』『真题』字样；必须有一节 Honest limitations 写明题库是 600 道自建题、benchmark 基线部分基于合成序列。中文版内容与英文版一致，不是机器翻译。"

step "w2-notebook" "完成 SPEC Wave 2 的 2.4：创建 examples/demo.ipynb，可一键运行（Cell 顺序：载入 demo_attempts 与 concepts、跑 diagnose、用 pandas 展示根因表、画掌握度条形图）。必须在本机实际执行过并保留输出（不要交付未运行的空 notebook）。报告实际执行结果。"

tag_wave v0.3.0 "Wave 2: visualization, demo GIF, bilingual README"
fi

# ============ WAVE 3：真实数据验证（硬闸门）============
if has_tag v0.4.0; then echo "skip wave3" >> "$LOG"; else
step "w3-download" "完成 SPEC Wave 3 的 3.1：写 scripts/download_assistments.py 下载 ASSISTments 2012-2013 skill-builder 数据集。若直连失败，尝试其他公开镜像；若全部失败，写清失败原因到 PROGRESS.md 并创建 data/real/DOWNLOAD_FAILED.md。不许卡住或静默跳过。"

step "w3-convert" "完成 SPEC Wave 3 的 3.2：写 scripts/convert_assistments.py，把原始数据转成 Attempt 格式，产出 data/real/assistments.jsonl 与 data/real/concepts_assistments.yaml。报告转换后 attempt 数、概念数、丢弃行数及丢弃原因。若 3.1 下载失败（存在 DOWNLOAD_FAILED.md），则本步明写跳过原因并把闸门标记为未通过。"

step "w3-compare" "完成 SPEC Wave 3 的 3.3：写 scripts/compare_bkt.py，在真实数据上做 5 折交叉验证，比较自写 BKT 与 pyBKT 的 AUC/RMSE（pybkt 用 pip 装到项目内，不污染全局）。**闸门判据**：若自写 BKT 与 pyBKT 的 AUC 差距 > 0.05，在 PROGRESS.md 写 [STOP] 并创建 STOP 文件，说明差距与初步排查结论，然后结束。若差距 < 0.02 则通过。报告两者真实 AUC 数值。"

step "w3-bench" "完成 SPEC Wave 3 的 3.4：更新 benchmark.md，把真实数据（ASSISTments）结果放表格最前面，合成序列结果降级为补充并标明 dataset 列。若 Wave 3 闸门未通过，明写原因，不伪造真实数据结果。"

tag_wave v0.4.0 "Wave 3: ASSISTments real-data validation"
fi

# ============ WAVE 4：软著材料 ============
if has_tag v0.5.0; then echo "skip wave4" >> "$LOG"; else
step "w4-source" "完成 SPEC Wave 4 的 4.1：写 scripts/extract_source.py，从 examdiag/ 抽取源码排版成 PDF（前 30 页 + 后 30 页，每页 50 行，页眉含软件全称与版本号 v0.5.0）。用 reportlab 或 matplotlib 生成 PDF（本机有）。产出 docs/copyright/source-60p.pdf，报告真实页数与源码总行数。"

step "w4-manual" "完成 SPEC Wave 4 的 4.2：写 docs/copyright/manual.md 并生成 PDF（30 页+，中文，ctex 或 reportlab）。必含：功能概述、运行环境、安装步骤、三张数据表字段说明、五大模块操作流程（BKT 拟合/诊断/补习路径/可视化/数据校验）、真实界面截图、版本说明。截图必须来自实际运行（可用 headless 截图 viz/report.html 与 CLI 输出）。"

step "w4-info" "完成 SPEC Wave 4 的 4.3：写 docs/copyright/INFO.md，十项申请信息齐全：软件全称、简称、版本号、开发完成日期、首次发表日期、开发方式、权利取得方式、硬件环境、软件环境、编程语言、源程序量行数（用 wc -l 实数）。"

tag_wave v0.5.0 "Wave 4: software copyright filing materials"
fi

# ============ WAVE 5：论文素材 ============
if has_tag v0.6.0; then echo "skip wave5" >> "$LOG"; else
step "w5-method" "完成 SPEC Wave 5 的 5.1：写 docs/METHOD.md，把 SPEC 第 5 节扩写成完整方法文档——BKT 前向后验推导、EM 的 E 步与 M 步逐步推导、根因诊断公式的来源与直觉、与 Reiter 诊断理论（最小碰集）的关系。每条公式必须有推导步骤，不许只给结论。"

step "w5-draft" "完成 SPEC Wave 5 的 5.2：写 docs/PAPER-DRAFT.md 技术报告草稿。结构：Abstract / Introduction / Related Work（pyBKT、DKT、pyKT、Knowledge Space Theory）/ Method / Experiments / Limitations。硬约束：所有实验数字必须能追溯到 benchmark.md；Limitations 必须含 SPEC 5.2 列的三条；不声称投顶会。若 Wave 3 真实数据未成功，在 Experiments 里明写只用合成数据的局限。"

step "w5-cite" "完成 SPEC Wave 5 的 5.3：写 scripts/fetch_citations.py 从 arXiv API + Semantic Scholar 抓真实论文生成 docs/CITATIONS.bib（≥15 条，覆盖 pyBKT/DKT/pyKT/知识空间理论/诊断理论）。禁止手写 BibTeX。报告 grep -c '@' 的真实数字。"

tag_wave v0.6.0 "Wave 5: method documentation and technical report draft"
fi

# ============ WAVE 6：工程化 + 发布物料 ============
if has_tag v1.0.0; then echo "skip wave6" >> "$LOG"; else
step "w6-ci" "完成 SPEC Wave 6 的 6.1：创建 .github/workflows/ci.yml，push 与 PR 时跑 ruff check + pytest，Python 3.10/3.11/3.12 矩阵，安装依赖用 pip。确保 workflow 语法正确（可用 python -c 'import yaml; yaml.safe_load(open(...))' 校验）。"

step "w6-cov" "完成 SPEC Wave 6 的 6.2：跑 pytest --cov=examdiag --cov-report=term，报告真实覆盖率。若 < 85%，补测试到 ≥ 85%（补的测试必须真实断言，不许空跑）。把覆盖率数字与 CI 状态徽章加进 README。"

step "w6-pages" "完成 SPEC Wave 6 的 6.3：把 viz/report.html 部署到 GitHub Pages。方案：在仓库建 docs/ 目录放 index.html（复制 viz/report.html 并确保数据内联），用 gh api 开启 Pages（gh api -X POST repos/2422725977/exam-diag/pages -f source[branch]=main -f source[path]=/docs），然后把 Pages URL 写进 README 的 Website 字段。报告真实 URL 与可访问性检查结果。"

step "w6-templates" "完成 SPEC Wave 6 的 6.4：创建 .github/ISSUE_TEMPLATE/bug_report.md 与 feature_request.md、CONTRIBUTING.md、CODE_OF_CONDUCT.md。内容用英文，简洁实用，不要模板化空话。"

step "w6-launch" "完成 SPEC Wave 6 的 6.5：写 docs/LAUNCH.md，含中文版（小红书/知乎/B站）与英文版（HN/Reddit）两套发布文案，每套 3 个标题候选 + 正文 + 配图说明 + 明确的发布时机建议。文案必须如实描述（600 道自建题、合成+真实双基线），禁止夸大。文件开头标注『人工执行：Agent 只写文案，不代发』。"

tag_wave v1.0.0 "v1.0.0: CI, coverage, Pages, launch materials"
fi

echo "" >> "$LOG"
echo "===== ALL WAVES DONE $(date '+%F %T') =====" >> "$LOG"
