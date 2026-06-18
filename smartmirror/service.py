"""High-level mirror service tying together storage, engine and watcher."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from .config import MirrorConfig
from .logger import get_logger
from .storage_manager import StorageManager, StorageUsage
from .sync_engine import SyncEngine, SyncStats
from .versioning import VersionManager
from .watcher import FileWatcher

log = get_logger("service")

STOPPED = "stopped"
STARTING = "starting"
RUNNING = "running"
PAUSED = "paused"
ERROR = "error"

StatusListener = Callable[["ServiceStatus"], None]


@dataclass
class ServiceStatus:
    state: str
    source_path: str
    mirror_path: str
    usage: StorageUsage
    stats: SyncStats
    message: str = ""
    watching: bool = False


class MirrorService:
    """Owns the lifecycle of a mirroring session."""

    def __init__(self, config: MirrorConfig) -> None:
        self.config = config
        self.storage = StorageManager(config.mirror_path, config.allocated_bytes)
        self.versioning = VersionManager(
            config.mirror_path, config.max_versions, config.versioning_enabled
        )
        self.engine = SyncEngine(
            config, self.storage, self.versioning, on_event=self._on_engine_event
        )
        self.watcher: FileWatcher | None = None
        self.state = STOPPED
        self.message = ""
        self._status_listeners: list[StatusListener] = []
        self._log_listeners: list[Callable[[str, str], None]] = []
        self._lock = threading.Lock()
        self._storage_warned = False

    # -- configuration ------------------------------------------------------
    def reconfigure(self, config: MirrorConfig) -> None:
        """Apply a new configuration. Must be stopped first."""
        if self.state in (RUNNING, PAUSED, STARTING):
            self.stop()
        self.config = config
        self.storage.set_mirror_path(config.mirror_path)
        self.storage.set_allocation(config.allocated_bytes)
        self.versioning.configure(
            config.mirror_path, config.max_versions, config.versioning_enabled
        )
        self.engine = SyncEngine(
            config, self.storage, self.versioning, on_event=self._on_engine_event
        )
        self._notify()

    # -- listeners ----------------------------------------------------------
    def add_status_listener(self, listener: StatusListener) -> None:
        self._status_listeners.append(listener)

    def add_log_listener(self, listener: Callable[[str, str], None]) -> None:
        self._log_listeners.append(listener)

    def _on_engine_event(self, level: str, message: str) -> None:
        for listener in list(self._log_listeners):
            try:
                listener(level, message)
            except Exception:  # pragma: no cover
                pass
        self._notify()

    def _notify(self) -> None:
        status = self.status()
        for listener in list(self._status_listeners):
            try:
                listener(status)
            except Exception:  # pragma: no cover
                pass

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        with self._lock:
            if self.state in (RUNNING, STARTING):
                return
            problems = self.config.validate()
            if problems:
                self.state = ERROR
                self.message = "; ".join(problems)
                log.error("Cannot start: %s", self.message)
                self._notify()
                return
            self.state = STARTING
            self.message = ""
        self._notify()
        thread = threading.Thread(target=self._start_worker, daemon=True)
        thread.start()

    def _start_worker(self) -> None:
        try:
            self.engine.full_sync(prune=True)
            self.engine.start()
            self.watcher = FileWatcher(self.config.source_path, self.engine)
            self.watcher.start()
            with self._lock:
                if self.config.paused:
                    self.engine.pause()
                    self.state = PAUSED
                else:
                    self.state = RUNNING
            log.info("Mirror service started (%s)", self.state)
        except Exception as exc:  # pragma: no cover - defensive
            with self._lock:
                self.state = ERROR
                self.message = str(exc)
            log.exception("Failed to start mirror service")
        self._notify()

    def pause(self) -> None:
        with self._lock:
            if self.state != RUNNING:
                return
            self.engine.pause()
            self.state = PAUSED
            self.config.paused = True
        log.info("Mirror service paused")
        self._notify()

    def resume(self) -> None:
        with self._lock:
            if self.state != PAUSED:
                return
            self.engine.resume()
            self.state = RUNNING
            self.config.paused = False
        log.info("Mirror service resumed")
        self._notify()

    def stop(self) -> None:
        with self._lock:
            if self.state == STOPPED:
                return
            if self.watcher is not None:
                self.watcher.stop()
                self.watcher = None
            self.engine.stop()
            self.state = STOPPED
        log.info("Mirror service stopped")
        self._notify()

    def restore(
        self,
        overwrite: bool = False,
        on_conflict: Callable[[str], bool] | None = None,
    ) -> SyncStats:
        log.info("Restore requested (overwrite=%s)", overwrite)
        return self.engine.restore(overwrite=overwrite, on_conflict=on_conflict)

    def run_full_sync(self) -> SyncStats:
        return self.engine.full_sync(prune=True)

    # -- storage alerts -----------------------------------------------------
    def check_storage_alert(self) -> str | None:
        """Return a one-shot warning message when the mirror zone crosses the
        configured fill threshold (e.g. 90%); ``None`` otherwise.

        The message is emitted only once per crossing: the latch resets after
        usage drops a few points back below the threshold.
        """
        threshold = float(getattr(self.config, "storage_warn_percent", 90.0))
        pct = self.storage.usage().percent_used
        if pct >= threshold:
            if not self._storage_warned:
                self._storage_warned = True
                msg = (
                    f"Mirror zone is {pct:.0f}% full (limit {threshold:.0f}%). "
                    f"{self.config.label()}: increase the allocation or free space."
                )
                log.warning(msg)
                return msg
        elif pct < max(0.0, threshold - 5.0):
            self._storage_warned = False
        return None

    # -- status -------------------------------------------------------------
    def status(self) -> ServiceStatus:
        return ServiceStatus(
            state=self.state,
            source_path=self.config.source_path,
            mirror_path=self.config.mirror_path,
            usage=self.storage.usage(),
            stats=self.engine.stats,
            message=self.message,
            watching=self.watcher.is_alive() if self.watcher else False,
        )

    def run_forever(self, poll_interval: float = 1.0) -> None:
        """Block the calling thread until interrupted (used by the CLI)."""
        self.start()
        try:
            while True:
                time.sleep(poll_interval)
        except KeyboardInterrupt:  # pragma: no cover - interactive
            log.info("Interrupted; shutting down.")
        finally:
            self.stop()
