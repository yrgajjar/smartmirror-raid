from __future__ import annotations

from smartmirror.config import MirrorConfig, load_config, save_config


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config = MirrorConfig(
        source_path=str(tmp_path / "src"),
        mirror_path=str(tmp_path / "mir"),
        allocated_bytes=123456,
        versioning_enabled=False,
        max_versions=5,
        hash_verify=False,
    )
    save_config(config, path)
    loaded = load_config(path)
    assert loaded == config


def test_load_missing_returns_defaults(tmp_path):
    loaded = load_config(tmp_path / "missing.json")
    assert loaded == MirrorConfig()


def test_from_dict_ignores_unknown_keys():
    config = MirrorConfig.from_dict({"source_path": "/x", "bogus": 1})
    assert config.source_path == "/x"


def test_validate_reports_problems(tmp_path):
    problems = MirrorConfig().validate()
    assert any("Source" in p for p in problems)
    assert any("Mirror" in p for p in problems)


def test_validate_same_path(tmp_path):
    same = str(tmp_path)
    config = MirrorConfig(source_path=same, mirror_path=same)
    problems = config.validate()
    assert any("different" in p for p in problems)


def test_validate_clean(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    config = MirrorConfig(
        source_path=str(src), mirror_path=str(tmp_path / "mir")
    )
    assert config.validate() == []
