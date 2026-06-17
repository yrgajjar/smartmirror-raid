"""Real-time file-system monitoring using watchdog."""

from __future__ import annotations

from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from .logger import get_logger
from .sync_engine import DELETE, MOVE, UPSERT, SyncEngine, SyncEvent

log = get_logger("watcher")


class _EngineEventHandler(FileSystemEventHandler):
    """Translates watchdog events into engine sync events."""

    def __init__(self, engine: SyncEngine) -> None:
        self.engine = engine

    def on_created(self, event: FileSystemEvent) -> None:
        self.engine.enqueue(
            SyncEvent(UPSERT, str(event.src_path), is_directory=event.is_directory)
        )

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self.engine.enqueue(SyncEvent(UPSERT, str(event.src_path)))

    def on_deleted(self, event: FileSystemEvent) -> None:
        self.engine.enqueue(
            SyncEvent(DELETE, str(event.src_path), is_directory=event.is_directory)
        )

    def on_moved(self, event: FileSystemEvent) -> None:
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

    def __init__(self, source_path: str | Path, engine: SyncEngine) -> None:
        self.source_path = Path(source_path)
        self.engine = engine
        self._observer: BaseObserver | None = None

    def start(self) -> None:
        if self._observer is not None:
            return
        observer = Observer()
        observer.schedule(
            _EngineEventHandler(self.engine), str(self.source_path), recursive=True
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
        log.info("Stopped watching %s", self.source_path)

    def is_alive(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
