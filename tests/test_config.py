"""config.py 测试：默认值、TOML 加载、优先级与失败路径。"""

import pytest

from examdiag.config import ExamDiagConfig, config_search_paths, load_config


def test_defaults():
    cfg = ExamDiagConfig()
    assert cfg.diagnose.top_n == 3
    assert cfg.diagnose.mastery_threshold == 0.5
    assert cfg.srs.max_per_day == 20
    assert cfg.report.output_dir.name == "report_out"


def test_search_paths_order():
    paths = config_search_paths()
    assert len(paths) == 2
    assert paths[0].name == ".examdiag.toml"
    assert paths[0] != paths[1]


def test_load_explicit_toml(tmp_path):
    cfg_file = tmp_path / "my.toml"
    cfg_file.write_text(
        "[diagnose]\ntop_n = 5\nmastery_threshold = 0.4\n"
        "[srs]\nmax_per_day = 7\n"
        "[report]\noutput_dir = 'out'\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert cfg.diagnose.top_n == 5
    assert cfg.diagnose.mastery_threshold == 0.4
    assert cfg.srs.max_per_day == 7
    assert cfg.report.output_dir.name == "out"


def test_load_missing_explicit_path_raises():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/examdiag.toml")


def test_invalid_value_rejected(tmp_path):
    cfg_file = tmp_path / "bad.toml"
    cfg_file.write_text("[diagnose]\ntop_n = 99\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(cfg_file)


def test_malformed_toml_rejected(tmp_path):
    cfg_file = tmp_path / "broken.toml"
    cfg_file.write_text("this is not toml {{{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(cfg_file)


def test_no_config_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # 当前目录无配置
    monkeypatch.setenv("HOME", str(tmp_path))  # 主目录也无配置
    cfg = load_config()
    assert cfg == ExamDiagConfig()


def test_cwd_config_beats_home(tmp_path, monkeypatch):
    (tmp_path / ".examdiag.toml").write_text("[diagnose]\ntop_n = 4\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_config()
    assert cfg.diagnose.top_n == 4


def test_version_constant_matches_pyproject():
    from pathlib import Path

    import examdiag
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert f'version = "{examdiag.__version__}"' in text
    assert examdiag.__version__ == "0.6.0"
