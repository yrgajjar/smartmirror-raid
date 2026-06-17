from __future__ import annotations

import time

from smartmirror.config import MirrorConfig
from smartmirror.service import PAUSED, RUNNING, STOPPED, MirrorService

from .helpers import write_file


def _wait_for_state(service, state, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        if service.state == state:
            return True
        time.sleep(0.05)
    return False


def test_service_lifecycle(tmp_path):
    source = tmp_path / "source"
    mirror = tmp_path / "mirror"
    source.mkdir()
    write_file(source / "a.txt", "hello")
    config = MirrorConfig(
        source_path=str(source),
        mirror_path=str(mirror),
        allocated_bytes=10_000_000,
    )
    service = MirrorService(config)
    try:
        service.start()
        assert _wait_for_state(service, RUNNING), service.state
        # Initial full sync mirrored the existing file.
        assert (mirror / "a.txt").read_text() == "hello"

        service.pause()
        assert service.state == PAUSED
        service.resume()
        assert service.state == RUNNING
    finally:
        service.stop()
    assert service.state == STOPPED


def test_service_start_invalid_config_sets_error(tmp_path):
    service = MirrorService(MirrorConfig())
    service.start()
    # Validation failure is synchronous.
    assert service.state == "error"
    assert service.status().message


def test_service_realtime_sync(tmp_path):
    source = tmp_path / "source"
    mirror = tmp_path / "mirror"
    source.mkdir()
    config = MirrorConfig(
        source_path=str(source),
        mirror_path=str(mirror),
        allocated_bytes=10_000_000,
    )
    service = MirrorService(config)
    try:
        service.start()
        assert _wait_for_state(service, RUNNING), service.state
        write_file(source / "live.txt", "created at runtime")
        # Allow the OS watcher + queue to propagate the change.
        end = time.time() + 8.0
        target = mirror / "live.txt"
        while time.time() < end and not target.exists():
            time.sleep(0.1)
        assert target.exists(), "watcher did not propagate new file"
        assert target.read_text() == "created at runtime"
    finally:
        service.stop()
