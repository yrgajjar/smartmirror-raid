from __future__ import annotations

import time

from smartmirror import sync_engine
from smartmirror.config import MirrorConfig
from smartmirror.service import MirrorService
from smartmirror.watcher import Debouncer

from .helpers import make_engine, write_file


def test_locked_file_is_retried_then_succeeds(tmp_path, monkeypatch):
    source, mirror, engine = make_engine(tmp_path)
    engine.retry_delay = 0
    src = write_file(source / "a.txt", "data")

    real_copy = sync_engine.shutil.copy2
    calls = {"n": 0}

    def flaky(s, d, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError(13, "file is locked")
        return real_copy(s, d, *args, **kwargs)

    monkeypatch.setattr(sync_engine.shutil, "copy2", flaky)

    result = engine.upsert_file(src)

    assert result == "copied"
    assert calls["n"] == 2  # failed once, retried once
    assert engine.stats.errors == 0
    assert (mirror / "a.txt").read_text() == "data"


def test_locked_file_eventually_reports_error(tmp_path, monkeypatch):
    source, mirror, engine = make_engine(tmp_path)
    engine.retry_delay = 0
    engine.max_retries = 2
    src = write_file(source / "a.txt", "data")

    def always_fail(s, d, *args, **kwargs):
        raise PermissionError(13, "still locked")

    monkeypatch.setattr(sync_engine.shutil, "copy2", always_fail)

    result = engine.upsert_file(src)

    assert result == "error"
    assert engine.stats.errors == 1
    # The temporary file must never be left behind.
    assert not (mirror / "a.txt.smtmp").exists()
    assert not (mirror / "a.txt").exists()


def test_no_partial_file_on_failure(tmp_path, monkeypatch):
    source, mirror, engine = make_engine(tmp_path)
    engine.retry_delay = 0
    engine.max_retries = 0
    src = write_file(source / "a.txt", "data")

    def fail(s, d, *args, **kwargs):
        raise OSError(5, "I/O error")  # non-transient

    monkeypatch.setattr(sync_engine.shutil, "copy2", fail)
    result = engine.upsert_file(src)

    assert result == "error"
    assert not (mirror / "a.txt").exists()
    assert not (mirror / "a.txt.smtmp").exists()


def test_debouncer_coalesces_bursts():
    debouncer = Debouncer(0.1)
    count = {"n": 0}

    def bump() -> None:
        count["n"] += 1

    for _ in range(5):
        debouncer.schedule("key", bump)
    time.sleep(0.3)

    assert count["n"] == 1


def test_debouncer_zero_delay_fires_immediately():
    debouncer = Debouncer(0)
    count = {"n": 0}
    debouncer.schedule("key", lambda: count.__setitem__("n", count["n"] + 1))
    assert count["n"] == 1


def test_debouncer_cancel_prevents_fire():
    debouncer = Debouncer(0.1)
    count = {"n": 0}
    debouncer.schedule("key", lambda: count.__setitem__("n", count["n"] + 1))
    debouncer.cancel("key")
    time.sleep(0.2)
    assert count["n"] == 0


def test_storage_alert_is_one_shot(tmp_path):
    source = tmp_path / "source"
    mirror = tmp_path / "mirror"
    source.mkdir()
    mirror.mkdir()
    (mirror / "big.bin").write_bytes(b"x" * 950)
    config = MirrorConfig(
        source_path=str(source),
        mirror_path=str(mirror),
        allocated_bytes=1000,
        storage_warn_percent=90.0,
    )
    service = MirrorService(config)

    first = service.check_storage_alert()
    second = service.check_storage_alert()

    assert first is not None
    assert "full" in first
    assert second is None  # only warns once per crossing


def test_storage_alert_silent_when_below_threshold(tmp_path):
    source = tmp_path / "source"
    mirror = tmp_path / "mirror"
    source.mkdir()
    mirror.mkdir()
    (mirror / "small.bin").write_bytes(b"x" * 100)
    config = MirrorConfig(
        source_path=str(source),
        mirror_path=str(mirror),
        allocated_bytes=1000,
        storage_warn_percent=90.0,
    )
    service = MirrorService(config)
    assert service.check_storage_alert() is None
