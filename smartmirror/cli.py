"""Command line interface for SmartMirror RAID."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import autostart, paths
from .config import GIB, MirrorConfig, load_config, save_config
from .logger import get_logger, setup_logging
from .service import MirrorService
from .version import APP_NAME, NOT_REAL_RAID_WARNING, __version__

log = get_logger("cli")


def _human_bytes(num: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PiB"


def _apply_overrides(config: MirrorConfig, args: argparse.Namespace) -> MirrorConfig:
    if getattr(args, "source", None):
        config.source_path = str(Path(args.source).expanduser())
    if getattr(args, "mirror", None):
        config.mirror_path = str(Path(args.mirror).expanduser())
    if getattr(args, "size_gb", None) is not None:
        config.allocated_bytes = int(args.size_gb * GIB)
    if getattr(args, "no_versioning", False):
        config.versioning_enabled = False
    if getattr(args, "no_hash", False):
        config.hash_verify = False
    return config


def _print_warning() -> None:
    print(f"[{APP_NAME}] {NOT_REAL_RAID_WARNING}")


def cmd_status(args: argparse.Namespace) -> int:
    config = _apply_overrides(load_config(), args)
    service = MirrorService(config)
    status = service.status()
    usage = status.usage
    print(f"{APP_NAME} v{__version__}")
    print(f"  Source : {status.source_path or '(not set)'}")
    print(f"  Mirror : {status.mirror_path or '(not set)'}")
    print(f"  State  : {status.state}")
    print(
        f"  Usage  : {_human_bytes(usage.used_bytes)} / "
        f"{_human_bytes(usage.allocated_bytes)} "
        f"({usage.percent_used:.1f}% of allocation)"
    )
    print(f"  Disk free: {_human_bytes(usage.disk_free_bytes)}")
    print(f"  Auto-start: {'on' if autostart.is_enabled() else 'off'}")
    print(f"  Config : {paths.config_dir() / 'config.json'}")
    print(f"  Logs   : {paths.log_dir()}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    config = load_config()
    changed = any(
        getattr(args, attr, None) not in (None, False)
        for attr in ("source", "mirror", "size_gb", "no_versioning", "no_hash")
    )
    config = _apply_overrides(config, args)
    if getattr(args, "versions", None) is not None:
        config.max_versions = args.versions
        changed = True
    if getattr(args, "autostart", None) is not None:
        config.autostart_enabled = args.autostart == "on"
        autostart.set_enabled(config.autostart_enabled)
        changed = True
    if changed:
        save_config(config)
        print("Configuration saved.")
    for key, value in config.to_dict().items():
        print(f"  {key} = {value}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    config = _apply_overrides(load_config(), args)
    problems = config.validate()
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2
    save_config(config)
    _print_warning()
    service = MirrorService(config)
    if args.once:
        stats = service.run_full_sync()
        print(
            f"Done: {stats.copied} copied, {stats.skipped} unchanged, "
            f"{stats.deleted} removed, {stats.errors} errors."
        )
        return 1 if stats.errors else 0
    print("Watching for changes. Press Ctrl+C to stop.")
    service.run_forever()
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    config = _apply_overrides(load_config(), args)
    if not config.mirror_path:
        print("error: mirror path is not set", file=sys.stderr)
        return 2
    _print_warning()
    if not args.yes:
        print(
            "Restore will copy files from the mirror back into the source.\n"
            f"  Mirror: {config.mirror_path}\n"
            f"  Source: {config.source_path}"
        )
        if args.overwrite:
            print("Existing source files that differ WILL be overwritten.")
        else:
            print("Existing source files will be kept (use --overwrite to replace).")
        answer = input("Proceed? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 1
    service = MirrorService(config)
    stats = service.restore(overwrite=args.overwrite)
    print(
        f"Restore complete: {stats.copied} restored, {stats.skipped} skipped, "
        f"{stats.errors} errors."
    )
    return 1 if stats.errors else 0


def cmd_gui(args: argparse.Namespace) -> int:
    try:
        from .ui.app import run as run_gui
    except ImportError as exc:  # PySide6 not installed
        print(
            "error: GUI dependencies are not installed. Install with "
            "'pip install PySide6'.\n"
            f"  ({exc})",
            file=sys.stderr,
        )
        return 3
    return run_gui(start_in_tray=getattr(args, "tray", False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smartmirror",
        description=f"{APP_NAME} - software RAID-1 style mirroring. "
        f"{NOT_REAL_RAID_WARNING}",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--source", help="Source path to mirror.")
        p.add_argument("--mirror", help="Mirror destination path.")
        p.add_argument(
            "--size-gb", type=float, help="Allocated mirror size in GiB."
        )
        p.add_argument(
            "--no-versioning", action="store_true", help="Disable versioning."
        )
        p.add_argument(
            "--no-hash",
            action="store_true",
            help="Use size+mtime instead of content hashing.",
        )

    p_sync = sub.add_parser("sync", help="Run the mirror service (watch for changes).")
    add_common(p_sync)
    p_sync.add_argument(
        "--once", action="store_true", help="Run a single full sync and exit."
    )
    p_sync.set_defaults(func=cmd_sync)

    p_restore = sub.add_parser("restore", help="Restore data from mirror to source.")
    add_common(p_restore)
    p_restore.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite differing files in the source.",
    )
    p_restore.add_argument(
        "--yes", action="store_true", help="Do not prompt for confirmation."
    )
    p_restore.set_defaults(func=cmd_restore)

    p_status = sub.add_parser("status", help="Show current configuration and usage.")
    add_common(p_status)
    p_status.set_defaults(func=cmd_status)

    p_config = sub.add_parser("config", help="View or change saved configuration.")
    add_common(p_config)
    p_config.add_argument("--versions", type=int, help="Number of versions to keep.")
    p_config.add_argument(
        "--autostart", choices=("on", "off"), help="Enable/disable launch on login."
    )
    p_config.set_defaults(func=cmd_config)

    p_gui = sub.add_parser("gui", help="Launch the desktop UI (default).")
    p_gui.set_defaults(func=cmd_gui, tray=False)

    p_tray = sub.add_parser("tray", help="Launch minimised to the system tray.")
    p_tray.set_defaults(func=cmd_gui, tray=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    paths.ensure_app_dirs()
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        # No subcommand -> launch the GUI.
        args.func = cmd_gui
        args.tray = False
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
