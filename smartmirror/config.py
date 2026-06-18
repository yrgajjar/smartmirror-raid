"""Application configuration model and persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import paths

DEFAULT_ALLOCATION_BYTES = 50 * 1024**3  # 50 GiB
GIB = 1024**3


@dataclass
class MirrorConfig:
    """User configuration for a single mirror relationship."""

    source_path: str = ""
    mirror_path: str = ""
    # Optional human-readable label shown in the UI/CLI when several pairs exist.
    name: str = ""
    allocated_bytes: int = DEFAULT_ALLOCATION_BYTES
    versioning_enabled: bool = True
    max_versions: int = 3
    autostart_enabled: bool = False
    paused: bool = False
    # Verify file equality with a content hash (slower but precise). When False
    # the engine relies on size + modification time, which is faster.
    hash_verify: bool = True
    # glob patterns (matched against the path relative to the source) to ignore.
    ignore_patterns: list[str] = field(default_factory=list)
    # Reliability tuning. A locked/busy file is retried a few times before it is
    # reported as an error; rapid bursts of writes to the same file are coalesced
    # by waiting ``debounce_seconds`` of quiet before mirroring.
    max_retries: int = 3
    retry_delay: float = 0.5
    debounce_seconds: float = 0.4
    # Emit a warning once the mirror zone passes this percentage of its quota.
    storage_warn_percent: float = 90.0

    # -- validation helpers -------------------------------------------------
    def is_configured(self) -> bool:
        return bool(self.source_path) and bool(self.mirror_path)

    def validate(self) -> list[str]:
        """Return a list of human readable problems (empty means valid)."""
        problems: list[str] = []
        if not self.source_path:
            problems.append("Source path is not set.")
        if not self.mirror_path:
            problems.append("Mirror path is not set.")
        if self.source_path and self.mirror_path:
            src = Path(self.source_path).resolve()
            dst = Path(self.mirror_path).resolve()
            if src == dst:
                problems.append("Source and mirror paths must be different.")
            elif src in dst.parents:
                # mirror nested inside source is allowed (the watcher ignores
                # the mirror subtree) but warn loudly about the implications.
                pass
            elif dst in src.parents:
                problems.append(
                    "Source path is inside the mirror path; this would create a loop."
                )
            if self.source_path and not src.exists():
                problems.append(f"Source path does not exist: {self.source_path}")
        if self.allocated_bytes <= 0:
            problems.append("Allocated mirror size must be greater than zero.")
        if self.max_versions < 1:
            problems.append("Maximum versions must be at least 1.")
        return problems

    def label(self) -> str:
        """Human-readable identifier for the pair (falls back to the paths)."""
        if self.name:
            return self.name
        if self.source_path:
            return Path(self.source_path).name or self.source_path
        return "(unconfigured)"

    # -- serialisation ------------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> MirrorConfig:
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# Languages the UI can be displayed in (code -> English label).
SUPPORTED_LANGUAGES = {"en": "English", "gu": "ગુજરાતી", "hi": "हिन्दी"}
DEFAULT_LANGUAGE = "en"


@dataclass
class AppConfig:
    """Top-level application configuration: a set of mirror pairs plus the
    global, app-wide preferences (UI language and launch-on-login)."""

    pairs: list[MirrorConfig] = field(default_factory=list)
    autostart_enabled: bool = False
    language: str = DEFAULT_LANGUAGE

    def is_configured(self) -> bool:
        return any(p.is_configured() for p in self.pairs)

    def to_dict(self) -> dict:
        return {
            "pairs": [p.to_dict() for p in self.pairs],
            "autostart_enabled": self.autostart_enabled,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        # New multi-pair format.
        if "pairs" in data:
            pairs = [MirrorConfig.from_dict(p) for p in data.get("pairs", [])]
            language = data.get("language", DEFAULT_LANGUAGE)
            if language not in SUPPORTED_LANGUAGES:
                language = DEFAULT_LANGUAGE
            return cls(
                pairs=pairs,
                autostart_enabled=bool(data.get("autostart_enabled", False)),
                language=language,
            )
        # Backward compatibility: migrate an old single-pair config file.
        pair = MirrorConfig.from_dict(data)
        autostart = bool(data.get("autostart_enabled", False))
        pairs = [pair] if (pair.source_path or pair.mirror_path) else []
        return cls(pairs=pairs, autostart_enabled=autostart)


def default_config_path() -> Path:
    return paths.config_dir() / "config.json"


def load_config(path: Path | None = None) -> MirrorConfig:
    path = path or default_config_path()
    if not path.exists():
        return MirrorConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return MirrorConfig()
    return MirrorConfig.from_dict(data)


def save_config(config: MirrorConfig, path: Path | None = None) -> None:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(path)


def load_app_config(path: Path | None = None) -> AppConfig:
    path = path or default_config_path()
    if not path.exists():
        return AppConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return AppConfig()
    if not isinstance(data, dict):
        return AppConfig()
    return AppConfig.from_dict(data)


def save_app_config(config: AppConfig, path: Path | None = None) -> None:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(path)
