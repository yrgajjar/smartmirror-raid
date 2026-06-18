"""Queue-based incremental mirroring engine.

The engine is deliberately independent of any UI framework so it can be unit
tested and driven from the CLI. File-system events are pushed onto a queue and
processed by a single worker thread, which keeps the mirror consistent and
avoids duplicate concurrent writes.
"""

from __future__ import annotations

import errno
import fnmatch
import hashlib
import os
import queue
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import MirrorConfig
from .logger import get_logger
from .storage_manager import StorageFullError, StorageManager
from .versioning import VersionManager

log = get_logger("sync")

# Actions understood by the engine.
UPSERT = "upsert"
DELETE = "delete"
MOVE = "move"

EventCallback = Callable[[str, str], None]  # (level, message)

# Errno values that indicate a temporary condition (a file held open by another
# process, a busy resource, ...) and are therefore worth retrying.
_TRANSIENT_ERRNOS = {errno.EACCES, errno.EBUSY, errno.EAGAIN, errno.ETXTBSY}
if hasattr(errno, "EPERM"):
    _TRANSIENT_ERRNOS.add(errno.EPERM)


def _is_transient(exc: OSError) -> bool:
    # On Windows a sharing violation surfaces as winerror 32/33.
    winerror = getattr(exc, "winerror", None)
    if winerror in (32, 33):
        return True
    return exc.errno in _TRANSIENT_ERRNOS


@dataclass
class SyncEvent:
    action: str
    src_path: str
    dest_path: str | None = None  # destination for MOVE events
    is_directory: bool = False


@dataclass
class SyncStats:
    copied: int = 0
    deleted: int = 0
    skipped: int = 0
    moved: int = 0
    errors: int = 0
    bytes_copied: int = 0
    last_event_time: float = 0.0


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SyncEngine:
    """Mirrors files from a source tree into a mirror directory."""

    def __init__(
        self,
        config: MirrorConfig,
        storage: StorageManager,
        versioning: VersionManager,
        on_event: EventCallback | None = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.versioning = versioning
        self.on_event = on_event
        self.stats = SyncStats()

        self.source = Path(config.source_path)
        self.mirror = Path(config.mirror_path)
        self.max_retries = max(0, int(getattr(config, "max_retries", 3)))
        self.retry_delay = max(0.0, float(getattr(config, "retry_delay", 0.5)))

        self._queue: queue.Queue[SyncEvent] = queue.Queue()
        self._pending: set[tuple[str, str]] = set()
        self._pending_lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._resume = threading.Event()
        self._resume.set()

    # -- path helpers -------------------------------------------------------
    def _rel(self, path: Path) -> str | None:
        try:
            return os.path.relpath(Path(path).resolve(), self.source.resolve())
        except ValueError:
            return None

    def _is_within_source(self, path: Path) -> bool:
        rel = self._rel(path)
        return rel is not None and not rel.startswith("..")

    def mirror_for(self, rel: str) -> Path:
        return self.mirror / rel

    def should_ignore(self, path: str | Path) -> bool:
        path = Path(path)
        resolved = path.resolve()
        mirror_resolved = self.mirror.resolve()
        # Never mirror the mirror zone into itself.
        if resolved == mirror_resolved or mirror_resolved in resolved.parents:
            return True
        if self.versioning.is_versions_path(resolved):
            return True
        rel = self._rel(path)
        if rel is None or rel.startswith(".."):
            return True
        for pattern in self.config.ignore_patterns:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern):
                return True
        return False

    # -- change detection ---------------------------------------------------
    def files_differ(self, src: Path, dst: Path) -> bool:
        if not dst.exists():
            return True
        try:
            s = src.stat()
            d = dst.stat()
        except OSError:
            return True
        if s.st_size != d.st_size:
            return True
        if self.config.hash_verify:
            try:
                return _sha256(src) != _sha256(dst)
            except OSError:
                return True
        # No hashing: rely on modification time. copy2 preserves mtime, so an
        # identical mirror file has a matching mtime.
        return abs(s.st_mtime - d.st_mtime) > 1.0

    # -- core operations (synchronous) -------------------------------------
    def _emit(self, level: str, message: str) -> None:
        getattr(log, level, log.info)(message)
        if self.on_event:
            try:
                self.on_event(level, message)
            except Exception:  # pragma: no cover
                pass

    def upsert_file(self, src: str | Path) -> str:
        src = Path(src)
        if self.should_ignore(src):
            return "ignored"
        if src.is_dir():
            rel = self._rel(src)
            if rel and not rel.startswith(".."):
                self.mirror_for(rel).mkdir(parents=True, exist_ok=True)
            return "dir"
        if not src.is_file():
            return "missing"
        rel = self._rel(src)
        if rel is None or rel.startswith(".."):
            return "outside"
        dst = self.mirror_for(rel)
        if not self.files_differ(src, dst):
            self.stats.skipped += 1
            return "skipped"
        try:
            src_size = src.stat().st_size
        except OSError:
            return "missing"
        replacing = dst.stat().st_size if dst.exists() else 0
        try:
            self.storage.check_store(src_size, replacing)
        except StorageFullError as exc:
            self.stats.errors += 1
            self._emit("error", str(exc))
            return "full"
        if dst.exists() and self.config.versioning_enabled:
            self.versioning.store(dst, rel)
        result = self._copy_with_retry(src, dst, rel)
        if result == "copied":
            self.stats.copied += 1
            self.stats.bytes_copied += src_size
            self.stats.last_event_time = time.time()
            self._emit("info", f"Mirrored {rel}")
        return result

    # -- atomic copy with locked-file retry --------------------------------
    def _tmp_for(self, dst: Path) -> Path:
        return dst.with_name(dst.name + ".smtmp")

    def _cleanup_tmp(self, dst: Path) -> None:
        try:
            tmp = self._tmp_for(dst)
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass

    def _interruptible_sleep(self, seconds: float) -> None:
        if seconds > 0:
            self._stop.wait(seconds)

    def _atomic_copy(self, src: Path, dst: Path) -> None:
        """Copy ``src`` to ``dst`` via a temp file so a crash mid-copy never
        leaves a half-written destination."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._tmp_for(dst)
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)

    def _copy_with_retry(self, src: Path, dst: Path, rel: str) -> str:
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                self._atomic_copy(src, dst)
                return "copied"
            except OSError as exc:
                self._cleanup_tmp(dst)
                transient = isinstance(exc, PermissionError) or _is_transient(exc)
                if transient and attempt < attempts - 1 and not self._stop.is_set():
                    self._emit(
                        "warning",
                        f"{rel} is busy/locked; retry "
                        f"{attempt + 1}/{self.max_retries} in {self.retry_delay:g}s",
                    )
                    self._interruptible_sleep(self.retry_delay)
                    continue
                self.stats.errors += 1
                self._emit("error", f"Failed to mirror {rel}: {exc}")
                return "error"
        return "error"

    def delete_path(self, src: str | Path) -> str:
        src = Path(src)
        rel = self._rel(src)
        if rel is None or rel.startswith(".."):
            return "outside"
        dst = self.mirror_for(rel)
        if not dst.exists():
            return "absent"
        try:
            if dst.is_dir():
                shutil.rmtree(dst, ignore_errors=True)
            else:
                if self.config.versioning_enabled:
                    self.versioning.store(dst, rel)
                dst.unlink()
            self.stats.deleted += 1
            self.stats.last_event_time = time.time()
            self._emit("info", f"Removed {rel} from mirror")
            return "deleted"
        except OSError as exc:
            self.stats.errors += 1
            self._emit("error", f"Failed to remove {rel}: {exc}")
            return "error"

    def move_path(self, old_src: str | Path, new_src: str | Path) -> str:
        old_inside = self._is_within_source(Path(old_src))
        new_inside = new_src is not None and self._is_within_source(Path(new_src))
        if old_inside and new_inside:
            # Try a cheap rename inside the mirror; fall back to copy + delete.
            old_rel = self._rel(Path(old_src))
            new_rel = self._rel(Path(new_src))
            if old_rel and new_rel:
                old_dst = self.mirror_for(old_rel)
                new_dst = self.mirror_for(new_rel)
                try:
                    if old_dst.exists():
                        new_dst.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(old_dst, new_dst)
                        self.stats.moved += 1
                        self._emit("info", f"Moved {old_rel} -> {new_rel}")
                        return "moved"
                except OSError:
                    pass
            # Fall back to recomputing both sides.
            self.delete_path(old_src)
            return self.upsert_file(new_src)
        if old_inside and not new_inside:
            return self.delete_path(old_src)
        if new_inside:
            return self.upsert_file(new_src)
        return "ignored"

    # -- full sync ----------------------------------------------------------
    def full_sync(self, prune: bool = True) -> SyncStats:
        """Mirror the entire source tree. When ``prune`` is set, mirror files
        that no longer exist in the source are removed."""
        if not self.source.exists():
            self._emit("error", f"Source path does not exist: {self.source}")
            return self.stats
        self.mirror.mkdir(parents=True, exist_ok=True)
        self._emit("info", f"Starting full sync of {self.source}")

        seen: set[str] = set()
        for root, dirs, files in os.walk(self.source):
            root_path = Path(root)
            # Do not descend into the mirror zone if it is nested in the source.
            dirs[:] = [
                d for d in dirs if not self.should_ignore(root_path / d)
            ]
            for name in files:
                src_file = root_path / name
                if self.should_ignore(src_file):
                    continue
                rel = self._rel(src_file)
                if rel is None or rel.startswith(".."):
                    continue
                seen.add(os.path.normpath(rel))
                self.upsert_file(src_file)

        if prune:
            self._prune_mirror(seen)

        self._emit(
            "info",
            f"Full sync complete: {self.stats.copied} copied, "
            f"{self.stats.skipped} unchanged, {self.stats.deleted} removed, "
            f"{self.stats.errors} errors.",
        )
        return self.stats

    def _prune_mirror(self, seen_rel: set[str]) -> None:
        if not self.mirror.exists():
            return
        for root, _dirs, files in os.walk(self.mirror, topdown=False):
            root_path = Path(root)
            if self.versioning.is_versions_path(root_path):
                continue
            for name in files:
                mirror_file = root_path / name
                if name.endswith(".smtmp"):
                    self._cleanup_tmp(mirror_file.with_name(name[: -len(".smtmp")]))
                    continue
                if self.versioning.is_versions_path(mirror_file):
                    continue
                rel = os.path.normpath(os.path.relpath(mirror_file, self.mirror))
                if rel not in seen_rel:
                    try:
                        if self.config.versioning_enabled:
                            self.versioning.store(mirror_file, rel)
                        mirror_file.unlink()
                        self.stats.deleted += 1
                        self._emit("info", f"Pruned stale mirror file {rel}")
                    except OSError as exc:
                        self._emit("error", f"Failed to prune {rel}: {exc}")

    # -- recovery -----------------------------------------------------------
    def restore(
        self,
        overwrite: bool = False,
        on_conflict: Callable[[str], bool] | None = None,
    ) -> SyncStats:
        """Copy mirror contents back into the source (recovery mode).

        Existing source files are never overwritten unless ``overwrite`` is
        True or ``on_conflict(rel)`` returns True. This protects user data.
        """
        stats = SyncStats()
        if not self.mirror.exists():
            self._emit("error", "Mirror path does not exist; cannot restore.")
            return stats
        self.source.mkdir(parents=True, exist_ok=True)
        self._emit("info", "Starting restore from mirror...")
        for root, dirs, files in os.walk(self.mirror):
            root_path = Path(root)
            dirs[:] = [
                d for d in dirs
                if not self.versioning.is_versions_path(root_path / d)
            ]
            for name in files:
                mirror_file = root_path / name
                if self.versioning.is_versions_path(mirror_file):
                    continue
                rel = os.path.relpath(mirror_file, self.mirror)
                dst = self.source / rel
                if dst.exists():
                    same = not self.files_differ(mirror_file, dst)
                    if same:
                        stats.skipped += 1
                        continue
                    proceed = overwrite
                    if on_conflict is not None:
                        proceed = on_conflict(rel)
                    if not proceed:
                        stats.skipped += 1
                        self._emit("warning", f"Skipped existing file {rel}")
                        continue
                try:
                    self._atomic_copy(mirror_file, dst)
                    stats.copied += 1
                    self._emit("info", f"Restored {rel}")
                except OSError as exc:
                    self._cleanup_tmp(dst)
                    stats.errors += 1
                    self._emit("error", f"Failed to restore {rel}: {exc}")
        self._emit(
            "info",
            f"Restore complete: {stats.copied} restored, "
            f"{stats.skipped} skipped, {stats.errors} errors.",
        )
        return stats

    # -- queue / worker -----------------------------------------------------
    def enqueue(self, event: SyncEvent) -> None:
        key = (event.action, event.dest_path or event.src_path)
        with self._pending_lock:
            if key in self._pending:
                return
            self._pending.add(key)
        self._queue.put(event)

    def process_event(self, event: SyncEvent) -> str:
        if event.action == UPSERT:
            return self.upsert_file(event.src_path)
        if event.action == DELETE:
            return self.delete_path(event.src_path)
        if event.action == MOVE:
            return self.move_path(event.src_path, event.dest_path or "")
        return "unknown"

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._resume.set()
        self._worker = threading.Thread(
            target=self._worker_loop, name="sync-engine", daemon=True
        )
        self._worker.start()

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                event = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            # Hold the dequeued event until we are resumed, so pausing reliably
            # stops processing even for events already pulled off the queue.
            while not self._resume.is_set() and not self._stop.is_set():
                self._resume.wait(0.2)
            key = (event.action, event.dest_path or event.src_path)
            with self._pending_lock:
                self._pending.discard(key)
            try:
                if not self._stop.is_set():
                    self.process_event(event)
            except Exception as exc:  # pragma: no cover - defensive
                self.stats.errors += 1
                self._emit("error", f"Unexpected sync error: {exc}")
            finally:
                self._queue.task_done()

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    @property
    def is_paused(self) -> bool:
        return not self._resume.is_set()

    def stop(self) -> None:
        self._stop.set()
        self._resume.set()
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=5)
        self._worker = None

    def wait_until_idle(self, timeout: float | None = None) -> None:
        """Block until all queued events have been processed (used in tests)."""
        end = None if timeout is None else time.time() + timeout
        while not self._queue.empty():
            if end is not None and time.time() > end:
                break
            time.sleep(0.02)
        self._queue.join()
