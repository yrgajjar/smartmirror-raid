from __future__ import annotations

import time

from smartmirror.versioning import VersionManager


def test_store_keeps_max_versions(tmp_path):
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    target = mirror / "file.txt"
    manager = VersionManager(mirror, max_versions=3, enabled=True)

    for i in range(5):
        target.write_text(f"content-{i}", encoding="utf-8")
        manager.store(target, "file.txt")
        time.sleep(0.005)

    versions = manager.list_versions("file.txt")
    assert len(versions) == 3
    # The retained versions should be the most recent ones.
    contents = sorted(p.read_text(encoding="utf-8") for p in versions)
    assert contents == ["content-2", "content-3", "content-4"]


def test_disabled_versioning_does_nothing(tmp_path):
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    target = mirror / "file.txt"
    target.write_text("data", encoding="utf-8")
    manager = VersionManager(mirror, max_versions=3, enabled=False)
    assert manager.store(target, "file.txt") is None
    assert not manager.versions_root().exists()


def test_is_versions_path(tmp_path):
    manager = VersionManager(tmp_path)
    assert manager.is_versions_path(manager.versions_root() / "x")
    assert not manager.is_versions_path(tmp_path / "regular.txt")
