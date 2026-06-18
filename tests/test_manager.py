from __future__ import annotations

from smartmirror.config import AppConfig, MirrorConfig, load_app_config
from smartmirror.manager import MirrorManager


def _pair(tmp_path, name):
    src = tmp_path / name / "src"
    mir = tmp_path / name / "mir"
    src.mkdir(parents=True, exist_ok=True)
    return MirrorConfig(name=name, source_path=str(src), mirror_path=str(mir))


def test_manager_builds_one_service_per_pair(tmp_path):
    path = tmp_path / "config.json"
    app = AppConfig(pairs=[_pair(tmp_path, "a"), _pair(tmp_path, "b")])
    manager = MirrorManager(app, config_path=path)
    assert len(manager) == 2
    assert manager.labels() == ["a", "b"]


def test_manager_add_remove_pair_persists(tmp_path):
    path = tmp_path / "config.json"
    manager = MirrorManager(AppConfig(), config_path=path)
    idx = manager.add_pair(_pair(tmp_path, "docs"))
    assert idx == 0
    assert len(manager) == 1
    # Reload from disk to confirm it was saved.
    reloaded = load_app_config(path)
    assert reloaded.pairs[0].name == "docs"

    manager.remove_pair(0)
    assert len(manager) == 0
    assert load_app_config(path).pairs == []


def test_manager_update_pair(tmp_path):
    path = tmp_path / "config.json"
    manager = MirrorManager(AppConfig(pairs=[_pair(tmp_path, "a")]), config_path=path)
    updated = _pair(tmp_path, "renamed")
    manager.update_pair(0, updated)
    assert manager.labels() == ["renamed"]
    assert load_app_config(path).pairs[0].name == "renamed"


def test_manager_status_listener_tags_index(tmp_path):
    path = tmp_path / "config.json"
    manager = MirrorManager(
        AppConfig(pairs=[_pair(tmp_path, "a"), _pair(tmp_path, "b")]),
        config_path=path,
    )
    seen: list[int] = []
    manager.add_status_listener(lambda index, status: seen.append(index))
    # Trigger a status notification on the second service.
    manager.services[1]._notify()
    assert seen == [1]


def test_manager_set_language_persists(tmp_path):
    path = tmp_path / "config.json"
    manager = MirrorManager(AppConfig(), config_path=path)
    manager.set_language("hi")
    assert load_app_config(path).language == "hi"
