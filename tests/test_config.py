from __future__ import annotations

import json

from smartmirror.config import (
    AppConfig,
    MirrorConfig,
    load_app_config,
    load_config,
    save_app_config,
    save_config,
)


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


def test_app_config_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    app = AppConfig(
        pairs=[
            MirrorConfig(
                name="Documents",
                source_path=str(tmp_path / "a"),
                mirror_path=str(tmp_path / "a_mir"),
            ),
            MirrorConfig(
                source_path=str(tmp_path / "b"),
                mirror_path=str(tmp_path / "b_mir"),
            ),
        ],
        autostart_enabled=True,
        language="gu",
    )
    save_app_config(app, path)
    loaded = load_app_config(path)
    assert len(loaded.pairs) == 2
    assert loaded.pairs[0].name == "Documents"
    assert loaded.autostart_enabled is True
    assert loaded.language == "gu"


def test_app_config_migrates_legacy_single_pair(tmp_path):
    path = tmp_path / "config.json"
    legacy = {
        "source_path": str(tmp_path / "src"),
        "mirror_path": str(tmp_path / "mir"),
        "allocated_bytes": 555,
        "autostart_enabled": True,
        "max_versions": 4,
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")
    app = load_app_config(path)
    assert len(app.pairs) == 1
    assert app.pairs[0].source_path == str(tmp_path / "src")
    assert app.pairs[0].allocated_bytes == 555
    assert app.pairs[0].max_versions == 4
    # App-wide autostart should be lifted out of the legacy single pair.
    assert app.autostart_enabled is True


def test_app_config_invalid_language_falls_back(tmp_path):
    path = tmp_path / "config.json"
    app = AppConfig(language="zz")
    save_app_config(app, path)
    loaded = load_app_config(path)
    assert loaded.language == "en"
