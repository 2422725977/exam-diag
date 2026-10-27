# ruff: noqa: E501
"""下载 ASSISTments skill-builder 数据集（Wave 3 任务 3.1）。

策略：按候选 URL 列表依次尝试，每个请求限时（连接/下载双超时），全部失败则
写 DOWNLOAD_FAILED.md（含每次尝试的真实原因），绝不无限等待。

候选源（按优先级）：
  1-2. 官方 Google Sites 原始文件（skill_builder_data_corrected.csv / .csv）
  3.   hf-mirror.com 镜像 OloriBern/assistments-dataset（官方 corrected 版，64.4MB）
       —— Google Sites 在本机网络不可达时的实际落点
  4.   GitHub codeload 镜像 psp0/Metaverse_Edu_Platform（sakt/data/skill_builder_data.csv）

下载成功后校验：非空、以表头行开头、包含关键列（user_id/correct/skill）。
输出：data/real/raw/skill_builder_data.csv
运行：python scripts/download_assistments.py
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data/real/raw/skill_builder_data.csv"
HF_BASE = "https://hf-mirror.com/datasets/OloriBern/assistments-dataset/resolve/main"

CANDIDATES = [
    ("official-google-sites (corrected)",
     "https://sites.google.com/site/assistmentsdata/home/2009-2010-assistment-data/"
     "skill_builder_data_corrected.csv?attredirects=0"),
    ("official-google-sites (original)",
     "https://sites.google.com/site/assistmentsdata/home/2009-2010-assistment-data/"
     "skill_builder_data.csv?attredirects=0"),
    ("hf-mirror OloriBern/assistments-dataset (corrected)",
     f"{HF_BASE}/skill_builder_data_corrected.csv"),
    ("github-codeload psp0/Metaverse_Edu_Platform",
     "https://codeload.github.com/psp0/Metaverse_Edu_Platform/zip/refs/heads/main"),
]

REQUIRED_COLS = ("user_id", "correct", "skill")


def try_download(url: str, workdir: Path) -> tuple[Path | None, str]:
    """单候选下载。返回 (文件路径 | None, 结果说明)。限时 60s 连接 / 600s 总量。"""
    target = workdir / ("candidate_" + url.split("/")[-1].split("?")[0])
    cmd = [
        "curl", "-L", "--fail", "--silent", "--show-error",
        "--connect-timeout", "60", "--max-time", "600",
        "-o", str(target), url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=660)
    except subprocess.TimeoutExpired:
        return None, "timeout after 660s (killed)"
    if proc.returncode != 0:
        return None, f"curl rc={proc.returncode}: {proc.stderr.strip()[:300] or 'no stderr (blocked/empty response)'}"
    if not target.exists() or target.stat().st_size == 0:
        return None, "empty file"
    return target, f"ok ({target.stat().st_size / 1024 / 1024:.1f} MB)"


def validate(path: Path) -> tuple[bool, str]:
    head = path.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0].lower()
    missing = [c for c in REQUIRED_COLS if c not in head]
    if missing:
        return False, f"header check failed, missing columns {missing}; header={head[:160]}"
    return True, f"header ok ({head[:120]}...)"


def main() -> int:
    if DEST.exists() and DEST.stat().st_size > 1_000_000:
        print(f"already downloaded: {DEST} ({DEST.stat().st_size / 1024 / 1024:.1f} MB)")
        return 0
    DEST.parent.mkdir(parents=True, exist_ok=True)
    workdir = DEST.parent
    log: list[str] = ["# ASSISTments 下载报告", ""]

    for name, url in CANDIDATES:
        print(f"try: {name} ...", flush=True)
        got, msg = try_download(url, workdir)
        log.append(f"- **{name}** → {msg}")
        print(f"    {msg}", flush=True)
        if got is None:
            continue
        if name.startswith("github-codeload"):
            # zip 包：解开找 csv
            shutil.unpack_archive(got, workdir / "zip_extract")
            found = sorted((workdir / "zip_extract").rglob("skill_builder_data*.csv"))
            if not found:
                log.append("  - zip 内未找到 skill_builder_data*.csv")
                continue
            got = found[0]
        ok, why = validate(got)
        log.append(f"  - 校验: {why}")
        print(f"    validate: {why}", flush=True)
        if ok:
            shutil.copyfile(got, DEST)
            log.append(f"\n落盘：`{DEST.relative_to(ROOT)}`（{DEST.stat().st_size / 1024 / 1024:.1f} MB）")
            (workdir / "DOWNLOAD_LOG.md").write_text("\n".join(log) + "\n", encoding="utf-8")
            print(f"saved {DEST}")
            return 0

    log.append("\n全部候选失败（原因见上）。")
    (ROOT / "DOWNLOAD_FAILED.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("DOWNLOAD_FAILED.md written")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
