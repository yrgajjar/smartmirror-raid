from __future__ import annotations

import pytest

from smartmirror.storage_manager import StorageFullError, StorageManager


def test_directory_size(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 100)
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "b.txt").write_bytes(b"y" * 50)
    manager = StorageManager(tmp_path, 1000)
    assert manager.used_bytes() == 150


def test_can_store_within_allocation(tmp_path):
    manager = StorageManager(tmp_path, 1000)
    assert manager.can_store(500)
    assert manager.can_store(1000)


def test_can_store_exceeding_allocation(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 900)
    manager = StorageManager(tmp_path, 1000)
    # 900 used + 200 new = 1100 > 1000
    assert not manager.can_store(200)
    # replacing the existing file keeps us within budget
    assert manager.can_store(200, replacing_bytes=900)


def test_check_store_raises(tmp_path):
    manager = StorageManager(tmp_path, 10)
    with pytest.raises(StorageFullError):
        manager.check_store(100)


def test_usage_percent(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 250)
    manager = StorageManager(tmp_path, 1000)
    usage = manager.usage()
    assert usage.used_bytes == 250
    assert usage.allocated_bytes == 1000
    assert usage.percent_used == pytest.approx(25.0)
    assert usage.free_in_allocation == 750
