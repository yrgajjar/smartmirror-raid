"""Command line interface for SmartMirror RAID."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import autostart, paths
from .config import (
    GIB,
    SUPPORTED_LANGUAGES,
    AppConfig,
    MirrorConfig,
    load_app_config,
    save_app_config,
)
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


def _print_warning() -> None:
    print(f"[{APP_NAME}] {NOT_REAL_RAID_WARNING}")


def _apply_overrides(config: MirrorConfig, args: argparse.Namespace) -> MirrorConfig:
    if getattr(args, "source", None):
        config.source_path = str(Path(args.source).expanduser())
    if getattr(args, "mirror", None):
        config.mirror_path = str(Path(args.mirror).expanduser())
    if getattr(args, "size_gb", None) is not None:
        config.allocated_bytes = int(args.size_gb * GIB)
    if getattr(args, "name", None):
        config.name = args.name
    if getattr(args, "no_versioning", False):
        config.versioning_enabled = False
    if getattr(args, "no_hash", False):
        config.hash_verify = False
    return config


def _has_overrides(args: argparse.Namespace) -> bool:
    return any(
        getattr(args, attr, None) not in (None, False)
        for attr in ("source", "mirror", "size_gb", "name", "no_versioning", "no_hash")
    )


def _resolve_pair_index(app: AppConfig, token: str) -> int:
    """Resolve a ``--pair`` token (1-based index or name/label) to an index."""
    token = token.strip()
    if token.isdigit():
        idx = int(token) - 1
        if 0 <= idx < len(app.pairs):
            return idx
        raise SystemExit(f"error: pair index {token} is out of range")
    lowered = token.lower()
    for i, pair in enumerate(app.pairs):
        if pair.name.lower() == lowered or pair.label().lower() == lowered:
            return i
    raise SystemExit(f"error: no pair named '{token}'")


def _select_indices(app: AppConfig, args: argparse.Namespace) -> list[int]:
    token = getattr(args, "pair", None)
    if token:
        return [_resolve_pair_index(app, token)]
    return list(range(len(app.pairs)))


def _target_pair_index(app: AppConfig, args: argparse.Namespace) -> int:
    """Index to edit/create when overrides are supplied on the command line."""
    token = getattr(args, "pair", None)
    if token:
        return _resolve_pair_index(app, token)
    if len(app.pairs) == 1:
        return 0
    if not app.pairs:
        app.pairs.append(MirrorConfig())
        return 0
    raise SystemExit(
        "error: multiple pairs are configured; choose one with --pair NAME|INDEX"
    )


# -- commands ---------------------------------------------------------------
def _print_pair_status(index: int, config: MirrorConfig) -> None:
    service = MirrorService(config)
    status = service.status()
    usage = status.usage
    print(f"  [{index + 1}] {config.label()}")
    print(f"      Source : {status.source_path or '(not set)'}")
    print(f"      Mirror : {status.mirror_path or '(not set)'}")
    print(f"      State  : {status.state}")
    print(
        f"      Usage  : {_human_bytes(usage.used_bytes)} / "
        f"{_human_bytes(usage.allocated_bytes)} "
        f"({usage.percent_used:.1f}% of allocation)"
    )
    print(f"      Disk free: {_human_bytes(usage.disk_free_bytes)}")


def cmd_status(args: argparse.Namespace) -> int:
    app = load_app_config()
    if _has_overrides(args):
        idx = _target_pair_index(app, args)
        _apply_overrides(app.pairs[idx], args)
    print(f"{APP_NAME} v{__version__}")
    print(f"  Language  : {app.language}")
    print(f"  Auto-start: {'on' if autostart.is_enabled() else 'off'}")
    print(f"  Config    : {paths.config_dir() / 'config.json'}")
    print(f"  Logs      : {paths.log_dir()}")
    if not app.pairs:
        print("  (no mirror pairs configured)")
        return 0
    print(f"  Pairs     : {len(app.pairs)}")
    for idx in _select_indices(app, args):
        _print_pair_status(idx, app.pairs[idx])
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    app = load_app_config()
    changed = False

    if getattr(args, "language", None):
        if args.language not in SUPPORTED_LANGUAGES:
            print(
                f"error: unsupported language '{args.language}'. "
                f"Choose from: {', '.join(SUPPORTED_LANGUAGES)}",
                file=sys.stderr,
            )
            return 2
        app.language = args.language
        changed = True

    if getattr(args, "autostart", None) is not None:
        app.autostart_enabled = args.autostart == "on"
        autostart.set_enabled(app.autostart_enabled)
        changed = True

    if _has_overrides(args) or getattr(args, "versions", None) is not None:
        idx = _target_pair_index(app, args)
        _apply_overrides(app.pairs[idx], args)
        if getattr(args, "versions", None) is not None:
            app.pairs[idx].max_versions = args.versions
        changed = True

    if changed:
        save_app_config(app)
        print("Configuration saved.")

    print(f"language = {app.language}")
    print(f"autostart_enabled = {app.autostart_enabled}")
    for idx, pair in enumerate(app.pairs):
        print(f"[pair {idx + 1}] {pair.label()}")
        for key, value in pair.to_dict().items():
            print(f"    {key} = {value}")
    return 0


def cmd_pairs(args: argparse.Namespace) -> int:
    app = load_app_config()
    action = getattr(args, "action", "list") or "list"

    if action == "list":
        if not app.pairs:
            print("No mirror pairs configured.")
            return 0
        for idx, pair in enumerate(app.pairs):
            print(
                f"[{idx + 1}] {pair.label()} :: "
                f"{pair.source_path or '(no source)'} -> "
                f"{pair.mirror_path or '(no mirror)'}"
            )
        return 0

    if action == "add":
        if not args.source or not args.mirror:
            print("error: --source and --mirror are required to add a pair",
                  file=sys.stderr)
            return 2
        pair = _apply_overrides(MirrorConfig(), args)
        problems = pair.validate()
        if problems:
            for problem in problems:
                print(f"error: {problem}", file=sys.stderr)
            return 2
        app.pairs.append(pair)
        save_app_config(app)
        print(f"Added pair [{len(app.pairs)}] {pair.label()}.")
        return 0

    if action == "remove":
        if not getattr(args, "pair", None):
            print("error: --pair NAME|INDEX is required to remove a pair",
                  file=sys.stderr)
            return 2
        idx = _resolve_pair_index(app, args.pair)
        removed = app.pairs.pop(idx)
        save_app_config(app)
        print(f"Removed pair {removed.label()}.")
        return 0

    print(f"error: unknown pairs action '{action}'", file=sys.stderr)
    return 2


def cmd_sync(args: argparse.Namespace) -> int:
    app = load_app_config()
    if _has_overrides(args):
        idx = _target_pair_index(app, args)
        _apply_overrides(app.pairs[idx], args)
        save_app_config(app)

    indices = _select_indices(app, args)
    if not indices:
        print("error: no mirror pairs configured (use 'pairs add' or --source/--mirror)",
              file=sys.stderr)
        return 2

    # Validate the selected pairs up-front.
    invalid = False
    for idx in indices:
        problems = app.pairs[idx].validate()
        if problems:
            invalid = True
            print(f"error: pair '{app.pairs[idx].label()}':", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
    if invalid:
        return 2

    _print_warning()
    services = [MirrorService(app.pairs[idx]) for idx in indices]

    if args.once:
        total_errors = 0
        for service in services:
            stats = service.run_full_sync()
            print(
                f"[{service.config.label()}] {stats.copied} copied, "
                f"{stats.skipped} unchanged, {stats.deleted} removed, "
                f"{stats.errors} errors."
            )
            total_errors += stats.errors
        return 1 if total_errors else 0

    if len(services) == 1:
        print("Watching for changes. Press Ctrl+C to stop.")
        services[0].run_forever()
        return 0

    # Multiple pairs: start each watcher and idle until interrupted.
    print(f"Watching {len(services)} mirror pairs. Press Ctrl+C to stop.")
    for service in services:
        service.start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        for service in services:
            service.stop()
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    app = load_app_config()
    indices = _select_indices(app, args)
    if not indices:
        print("error: no mirror pairs configured", file=sys.stderr)
        return 2
    if len(indices) > 1 and not args.all:
        print(
            "error: multiple pairs configured; choose one with --pair NAME|INDEX "
            "or restore every pair with --all",
            file=sys.stderr,
        )
        return 2

    _print_warning()
    total_errors = 0
    for idx in indices:
        config = app.pairs[idx]
        if not config.mirror_path:
            print(f"error: pair '{config.label()}' has no mirror path",
                  file=sys.stderr)
            total_errors += 1
            continue
        if not args.yes:
            print(
                f"Restore '{config.label()}' from mirror back into the source.\n"
                f"  Mirror: {config.mirror_path}\n"
                f"  Source: {config.source_path}"
            )
            if args.overwrite:
                print("Existing source files that differ WILL be overwritten.")
            else:
                print("Existing source files will be kept (use --overwrite to replace).")
            answer = input("Proceed? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Skipped.")
                continue
        service = MirrorService(config)
        stats = service.restore(overwrite=args.overwrite)
        print(
            f"[{config.label()}] restore complete: {stats.copied} restored, "
            f"{stats.skipped} skipped, {stats.errors} errors."
        )
        total_errors += stats.errors
    return 1 if total_errors else 0


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
        p.add_argument("--name", help="Display name for the pair.")
        p.add_argument("--size-gb", type=float, help="Allocated mirror size in GiB.")
        p.add_argument(
            "--pair", help="Operate on a single pair (name or 1-based index)."
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
        "--all", action="store_true", help="Restore every configured pair."
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
    p_config.add_argument(
        "--language",
        choices=tuple(SUPPORTED_LANGUAGES),
        help="Set the UI language (en/gu/hi).",
    )
    p_config.set_defaults(func=cmd_config)

    p_pairs = sub.add_parser("pairs", help="List, add or remove mirror pairs.")
    p_pairs.add_argument(
        "action",
        nargs="?",
        choices=("list", "add", "remove"),
        default="list",
        help="What to do (default: list).",
    )
    p_pairs.add_argument("--source", help="Source path (for add).")
    p_pairs.add_argument("--mirror", help="Mirror path (for add).")
    p_pairs.add_argument("--name", help="Display name (for add).")
    p_pairs.add_argument("--size-gb", type=float, help="Allocated mirror size in GiB.")
    p_pairs.add_argument(
        "--pair", help="Pair to remove (name or 1-based index)."
    )
    p_pairs.set_defaults(func=cmd_pairs)

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
