"""File versioning: keep the last N copies of changed/removed mirror files."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .logger import get_logger

log = get_logger("versioning")

VERSIONS_DIRNAME = ".smartmirror_versions"


class VersionManager:
    """Stores historical copies of files inside the mirror zone.

    Versions live under ``<mirror>/.smartmirror_versions/<relative path>/`` and
    are named ``<timestamp>__<original name>``. Only ``max_versions`` copies are
    retained per file; older ones are pruned.
    """

    def __init__(
        self,
        mirror_root: str | Path,
        max_versions: int = 3,
        enabled: bool = True,
    ) -> None:
        self.mirror_root = Path(mirror_root)
        self.max_versions = max(1, int(max_versions))
        self.enabled = enabled

    def configure(
        self,
        mirror_root: str | Path | None = None,
        max_versions: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        if mirror_root is not None:
            self.mirror_root = Path(mirror_root)
        if max_versions is not None:
            self.max_versions = max(1, int(max_versions))
        if enabled is not None:
            self.enabled = enabled

    def versions_root(self) -> Path:
        return self.mirror_root / VERSIONS_DIRNAME

    def is_versions_path(self, path: str | Path) -> bool:
        path = Path(path)
        root = self.versions_root()
        try:
            return path == root or root in path.parents
        except OSError:
            return False

    def _version_dir_for(self, rel_path: str) -> Path:
        return self.versions_root() / rel_path

    def store(self, mirror_file: Path, rel_path: str) -> Path | None:
        """Snapshot the current content of ``mirror_file`` before it changes."""
        if not self.enabled:
            return None
        mirror_file = Path(mirror_file)
        if not mirror_file.is_file():
            return None
        version_dir = self._version_dir_for(rel_path)
        try:
            version_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
            dest = version_dir / f"{stamp}__{mirror_file.name}"
            shutil.copy2(mirror_file, dest)
            self._prune(version_dir)
            log.debug("Stored version %s", dest)
            return dest
        except OSError as exc:
            log.warning("Could not store version for %s: %s", rel_path, exc)
            return None

    def _prune(self, version_dir: Path) -> None:
        try:
            versions = sorted(
                (p for p in version_dir.iterdir() if p.is_file()),
                key=lambda p: p.stat().st_mtime,
            )
        except OSError:
            return
        while len(versions) > self.max_versions:
            oldest = versions.pop(0)
            try:
                oldest.unlink()
                log.debug("Pruned old version %s", oldest)
            except OSError:
                break

    def list_versions(self, rel_path: str) -> list[Path]:
        version_dir = self._version_dir_for(rel_path)
        if not version_dir.exists():
            return []
        return sorted(
            (p for p in version_dir.iterdir() if p.is_file()),
            key=lambda p: p.stat().st_mtime,
        )
