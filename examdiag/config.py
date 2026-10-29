"""用户配置加载：~/.examdiag.toml（或 ./.examdiag.toml），pydantic 强校验。

优先级：显式路径 > ./.examdiag.toml > ~/.examdiag.toml > 内置默认。
文件存在但解析失败或字段越界时抛 ValueError 并给出具体原因——不静默吞掉。
Python 3.10 无 tomllib：只有当真找到配置文件时才报错，纯默认使用不受影响。
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

try:  # Python ≥ 3.11
    import tomllib  # noqa: F401
    _HAS_TOMLLIB = True
except ModuleNotFoundError:  # pragma: no cover
    _HAS_TOMLLIB = False

CONFIG_FILENAME = ".examdiag.toml"


class DiagnoseConfig(BaseModel):
    top_n: int = Field(3, ge=1, le=10)
    mastery_threshold: float = Field(0.5, ge=0.0, le=1.0)


class SrsConfig(BaseModel):
    span: float = Field(6.0, ge=1.0, le=30.0)
    horizon: int = Field(7, ge=1, le=31)
    max_per_day: int = Field(20, ge=1, le=500)


class ReportConfig(BaseModel):
    output_dir: Path = Path("report_out")
    stem_head: int = Field(38, ge=10, le=200)


class ExamDiagConfig(BaseModel):
    diagnose: DiagnoseConfig = Field(default_factory=DiagnoseConfig)
    srs: SrsConfig = Field(default_factory=SrsConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)


def config_search_paths() -> list[Path]:
    """按优先级排列的配置文件候选路径。"""
    return [Path.cwd() / CONFIG_FILENAME, Path.home() / CONFIG_FILENAME]


def _read_toml(path: Path) -> dict:
    if not _HAS_TOMLLIB:
        raise ValueError(
            f"found config {path} but this Python (< 3.11) has no tomllib; "
            "use Python >= 3.11 or delete the config file"
        )
    import tomllib

    with open(path, "rb") as f:
        return tomllib.load(f)


def load_config(path: str | Path | None = None) -> ExamDiagConfig:
    """加载配置：显式路径 > 当前目录 > 用户主目录 > 默认值。"""
    if path is not None:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"config file not found: {p}")
        return ExamDiagConfig(**_read_toml(p))
    for candidate in config_search_paths():
        if candidate.exists():
            try:
                return ExamDiagConfig(**_read_toml(candidate))
            except Exception as e:
                raise ValueError(f"invalid config {candidate}: {e}") from e
    return ExamDiagConfig()
