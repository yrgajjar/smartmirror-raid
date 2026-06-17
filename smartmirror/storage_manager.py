"""Storage allocation and usage accounting for the mirror zone."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .logger import get_logger

log = get_logger("storage")


class StorageError(Exception):
    """Base class for storage related problems."""


class StorageFullError(StorageError):
    """Raised when an operation would exceed the allocated mirror size or disk."""


@dataclass
class StorageUsage:
    used_bytes: int
    allocated_bytes: int
    disk_free_bytes: int
    disk_total_bytes: int

    @property
    def free_in_allocation(self) -> int:
        return max(0, self.allocated_bytes - self.used_bytes)

    @property
    def percent_used(self) -> float:
        if self.allocated_bytes <= 0:
            return 0.0
        return min(100.0, 100.0 * self.used_bytes / self.allocated_bytes)


class StorageManager:
    """Tracks how much of the allocated mirror size is in use.

    The mirror zone is a directory on disk. We treat ``allocated_bytes`` as a
    soft quota for that directory and refuse writes that would exceed it (or
    that would exceed the real free space on the underlying disk).
    """

    def __init__(self, mirror_path: str | Path, allocated_bytes: int) -> None:
        self.mirror_path = Path(mirror_path)
        self.allocated_bytes = int(allocated_bytes)

    def set_mirror_path(self, mirror_path: str | Path) -> None:
        self.mirror_path = Path(mirror_path)

    def set_allocation(self, allocated_bytes: int) -> None:
        self.allocated_bytes = int(allocated_bytes)

    # -- measurement --------------------------------------------------------
    @staticmethod
    def directory_size(path: Path) -> int:
        total = 0
        if not path.exists():
            return 0
        for entry in path.rglob("*"):
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file():
                    total += entry.stat().st_size
            except OSError:
                # File vanished or is unreadable; ignore for accounting.
                continue
        return total

    def used_bytes(self) -> int:
        return self.directory_size(self.mirror_path)

    def _disk_usage(self):
        target = self.mirror_path
        # Walk up to the first existing parent so disk_usage does not fail
        # before the mirror directory has been created.
        while not target.exists() and target != target.parent:
            target = target.parent
        try:
            return shutil.disk_usage(target)
        except OSError:
            return None

    def disk_free_bytes(self) -> int:
        usage = self._disk_usage()
        return usage.free if usage else 0

    def disk_total_bytes(self) -> int:
        usage = self._disk_usage()
        return usage.total if usage else 0

    def usage(self) -> StorageUsage:
        return StorageUsage(
            used_bytes=self.used_bytes(),
            allocated_bytes=self.allocated_bytes,
            disk_free_bytes=self.disk_free_bytes(),
            disk_total_bytes=self.disk_total_bytes(),
        )

    # -- quota checks -------------------------------------------------------
    def can_store(
        self,
        additional_bytes: int,
        replacing_bytes: int = 0,
        *,
        used_bytes: int | None = None,
    ) -> bool:
        """Whether writing ``additional_bytes`` (replacing ``replacing_bytes``)
        fits inside both the allocation and the real free disk space."""
        current = self.used_bytes() if used_bytes is None else used_bytes
        projected = current - replacing_bytes + additional_bytes
        if projected > self.allocated_bytes:
            return False
        net_new = additional_bytes - replacing_bytes
        if net_new > 0 and net_new > self.disk_free_bytes():
            return False
        return True

    def check_store(
        self,
        additional_bytes: int,
        replacing_bytes: int = 0,
        *,
        used_bytes: int | None = None,
    ) -> None:
        if not self.can_store(
            additional_bytes, replacing_bytes, used_bytes=used_bytes
        ):
            raise StorageFullError(
                "Mirror zone is full: writing "
                f"{additional_bytes} bytes would exceed the allocated "
                f"{self.allocated_bytes} bytes (or the available disk space)."
            )
