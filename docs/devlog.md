# 开发日志（exam-diag）

> 本文档整理自项目开发过程记录（2026-10-27 至 2026-10-30）。完整的逐步提交
> 历史见 `git log`（40+ commits，每步一次提交与推送，是开发过程最原始的证据）；
> 数据格式见 docs/DATA_FORMAT.md，评测数字见 benchmark.md 与 data/real/。

## 时间线

**Day 1（2026-10-27/28）—— 引擎与数据。**
仓库公开（GitHub 2422725977/exam-diag）。按"引擎先行"的顺序完成：包骨架与
pydantic 数据模型（含 prereq 环检测）；纯 numpy 的 BKT 引擎（缩放前向-后向 +
Baum-Welch EM，2000 条合成序列参数恢复误差全部 < 0.012）；合成数据基准
（自写 BKT AUC 0.7872，优于近 3 次均值与全局均值两个基线）；四科知识图谱
240 概念（每科 60 节点，校验脚本逐项验收）与四科题库 600 道自建选择题
（分批生成、批后校验、全部标注 self-built）。打 tag v0.1.0。

**Day 2（2026-10-28 上午）—— 诊断能力。**
networkx DAG 操作层；根因诊断算法（score 传播分 + 症状过滤 + 掌握度升序）；
7 天复习计划；rich 命令行；单用户 500 条演示数据植入"树遍历→AVL"薄弱链，
验收断言"第一根因 = ds.tree.traverse"通过。打 tag v0.2.0。

**Day 2（2026-10-28 下午）—— 可视化与传播。**
单文件可视化报告（分层 SVG + mastery 渐变 + 点击查错题）；演示 GIF
（PIL 逐帧 + ffmpeg 调色板，帧内容全部来自真实命令输出）；双语 README；
演示笔记本。打 tag v0.3.0；随后多用户演示数据（三条不同方向薄弱链）与
GIF 重制（三根因同屏），打 tag v0.3.1。

**Day 3（2026-10-28 晚）—— 真实数据验证。**
下载 ASSISTments skill-builder（官方 Google Sites 在本机网络不可达，经
hf-mirror 镜像取回官方 corrected 版 61.4 MB）；转换为 274,590 条作答
（4,151 用户 / 101 技能）；5 折交叉验证对比自写 BKT 与 pyBKT 1.4.3——
AUC 0.7118 vs 0.7116，差距 0.0002，闸门（< 0.02）通过。benchmark.md 改为
真实数据优先。打 tag v0.4.0。

**Day 4（2026-10-30）—— 软著材料与功能增厚。**
整理软件著作权申请材料（源程序册 / 用户手册 / 申请信息）；随后核心包功能
增厚：报告导出模块（Markdown/CSV/Excel/HTML，命令 `examdiag report`）、
SM-2 复习调度器（EF 由掌握度初始化、种子间隔递增、每日队列上限 + 老化
防饿死）、用户配置文件（~/.examdiag.toml）。`examdiag --version` 输出
"exam-diag 考试错题根因诊断系统 V0.6.0"，与源代码常量、手册、源程序册页眉
形成四处一致的版本闭环。申请材料按 V0.6.0 全部重新生成。打 tag v0.6.0。

## 技术备忘

### pyBKT 1.4.3 兼容性垫片（复现真实数据评测时相关）

pyBKT 在 Python 3.14 + numpy ≥ 2 + 新版 sklearn 上有三处不兼容，均在
site-packages 内打了最小垫片（不涉及算法本身）：

1. `pyBKT/util/metrics.py` 指标探测逐项容错（sklearn ≥ 1.7 的部分指标拒绝
   list 输入，探测失败只意味着该指标不可用，不应让整个包导入崩溃）；
2. `pyBKT/fit/EM_fit.py` 对数似然赋值改为 `.item()`（numpy ≥ 2 禁止把 (1,1)
   数组赋给标量槽位）；
3. `Model(parallel=False)`：默认 multiprocessing 池在 macOS spawn 下信号量
   死锁（sample 实测 SemLock_acquire 挂起）——并行只影响执行方式不影响 EM 结果。

另注：pyBKT 对个别技能的 EM 有 divide-by-zero RuntimeWarning（其内部数值
处理），预测仍正常产出。

### BKT EM 退化与兜底

全对/全错的极短序列会让 EM 退化：例如全错序列把 p_S 顶到上界 0.99，拟合
为"已掌握但总失误"——与"未掌握"似然完全相同而后验相反。诊断模块检测到
拟合出的 p_S/p_G > 0.5 即回退默认参数做前向后验，保证全对→高、全错→低的
直觉排序。该设计记录于 examdiag/diagnose.py 的 `_mastery_of`。

### 根因排序的"症状过滤"

SPEC 5.3 的 score 公式衡量"未掌握程度 × 上游未掌握传播"，直接按分数排序
会偏向深层症状节点。实现采用两段式：先做症状过滤（候选若有掌握度 < 0.5
的有数据前置，则其失败可被上游解释，降为症状挂到根因的 explains 列表），
幸存者按掌握度升序 + 拓扑序取前 top_n——等价于"在每条失败链上取最上游
的破损概念作为根因"。

### SM-2 每日上限的饿死问题

每日队列上限 + 掌握度升序出队 + 弱项天天失败，会让被顺延的强项永久排队
（单元测试暴露）。修复：顺延项带老化计数，出队按"顺延次数多者优先"再按
掌握度升序。

### 环境事实

- 后台子代理并发上限为 1：并行启动的代理会在 ~250ms 内报
  `user concurrency limit exceeded`，多代理任务需串行流水线；
- 官方 Google Sites（ASSISTments 原始下载页）在本机网络不可达，curl 连接
  即失败；hf-mirror.com 可达，GitHub 主站可达但 raw.githubusercontent.com
  不可达（仓库文件用 codeload 或镜像取回）。

## 数据与验收基线（登记时的真实状态）

- 核心包 examdiag/ 1,727 行（schema / bkt / graph / diagnose / srs / report /
  config / eval / cli），tests/ 1,050 行 105 个单元测试，scripts/ 1,875 行；
- 四科知识图谱 240 概念 + 600 道自建题 + 三份演示作答数据，`validate_data.py all` 全 PASS；
- 合成基准：自写 BKT AUC 0.7872；真实数据（ASSISTments 27.4 万条）5 折 CV：
  自写 BKT AUC 0.7118 vs pyBKT 0.7116。
