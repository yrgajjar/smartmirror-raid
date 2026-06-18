"""Real-time file-system monitoring using watchdog."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from .logger import get_logger
from .sync_engine import DELETE, MOVE, UPSERT, SyncEngine, SyncEvent

log = get_logger("watcher")


class Debouncer:
    """Coalesces rapid repeated callbacks for the same key.

    A file being written (especially a large one) emits a burst of "modified"
    events. Rather than mirroring on every event we wait for ``delay`` seconds
    of quiet per path and only then fire once.
    """

    def __init__(self, delay: float) -> None:
        self.delay = max(0.0, float(delay))
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def schedule(self, key: str, callback: Callable[[], None]) -> None:
        if self.delay <= 0:
            callback()
            return

        def fire() -> None:
            with self._lock:
                self._timers.pop(key, None)
            callback()

        with self._lock:
            existing = self._timers.pop(key, None)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(self.delay, fire)
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def cancel(self, key: str) -> None:
        with self._lock:
            timer = self._timers.pop(key, None)
        if timer is not None:
            timer.cancel()

    def cancel_all(self) -> None:
        with self._lock:
            timers = list(self._timers.values())
            self._timers.clear()
        for timer in timers:
            timer.cancel()


class _EngineEventHandler(FileSystemEventHandler):
    """Translates watchdog events into engine sync events."""

    def __init__(self, engine: SyncEngine, debouncer: Debouncer) -> None:
        self.engine = engine
        self._debounce = debouncer

    def _debounced_upsert(self, path: str, is_directory: bool) -> None:
        # Directories are cheap (just a mkdir) so mirror them immediately;
        # files wait for the write burst to settle.
        if is_directory:
            self.engine.enqueue(SyncEvent(UPSERT, path, is_directory=True))
            return
        self._debounce.schedule(
            path, lambda: self.engine.enqueue(SyncEvent(UPSERT, path))
        )

    def on_created(self, event: FileSystemEvent) -> None:
        self._debounced_upsert(str(event.src_path), event.is_directory)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._debounced_upsert(str(event.src_path), False)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._debounce.cancel(str(event.src_path))
        self.engine.enqueue(
            SyncEvent(DELETE, str(event.src_path), is_directory=event.is_directory)
        )

    def on_moved(self, event: FileSystemEvent) -> None:
        self._debounce.cancel(str(event.src_path))
        self.engine.enqueue(
            SyncEvent(
                MOVE,
                str(event.src_path),
                dest_path=str(event.dest_path),
                is_directory=event.is_directory,
            )
        )


class FileWatcher:
    """Watches ``source_path`` recursively and feeds the sync engine."""

    def __init__(
        self,
        source_path: str | Path,
        engine: SyncEngine,
        debounce_seconds: float | None = None,
    ) -> None:
        self.source_path = Path(source_path)
        self.engine = engine
        if debounce_seconds is None:
            debounce_seconds = getattr(engine.config, "debounce_seconds", 0.4)
        self._debouncer = Debouncer(debounce_seconds)
        self._observer: BaseObserver | None = None

    def start(self) -> None:
        if self._observer is not None:
            return
        observer = Observer()
        observer.schedule(
            _EngineEventHandler(self.engine, self._debouncer),
            str(self.source_path),
            recursive=True,
        )
        observer.start()
        self._observer = observer
        log.info("Watching %s for changes", self.source_path)

    def stop(self) -> None:
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        self._debouncer.cancel_all()
        log.info("Stopped watching %s", self.source_path)

    def is_alive(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
