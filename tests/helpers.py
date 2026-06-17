"""Shared helpers for the test-suite."""

from __future__ import annotations

from pathlib import Path

from smartmirror.config import MirrorConfig
from smartmirror.storage_manager import StorageManager
from smartmirror.sync_engine import SyncEngine
from smartmirror.versioning import VersionManager


def write_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def make_engine(
    tmp_path: Path,
    allocated: int = 1_000_000_000,
    hash_verify: bool = True,
    versioning: bool = True,
) -> tuple[Path, Path, SyncEngine]:
    source = tmp_path / "source"
    mirror = tmp_path / "mirror"
    source.mkdir(parents=True, exist_ok=True)
    mirror.mkdir(parents=True, exist_ok=True)
    config = MirrorConfig(
        source_path=str(source),
        mirror_path=str(mirror),
        allocated_bytes=allocated,
        hash_verify=hash_verify,
        versioning_enabled=versioning,
        max_versions=3,
    )
    storage = StorageManager(str(mirror), allocated)
    version_mgr = VersionManager(str(mirror), 3, versioning)
    engine = SyncEngine(config, storage, version_mgr)
    return source, mirror, engine
