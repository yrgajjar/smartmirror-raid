# SmartMirror RAID

Cross-platform desktop app that simulates **RAID-1 style mirroring** on a single
machine using software-level file replication.

> ⚠️ **This is NOT real RAID.** SmartMirror RAID continuously copies files from a
> source folder into a "mirror zone" on disk. It is a backup/mirroring tool and
> does **not** provide hardware fault tolerance. If the physical disk fails,
> both copies can be lost. For true redundancy use hardware/OS RAID across
> separate disks.

![status](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-blue)

## Features

| # | Feature | Where |
|---|---------|-------|
| 1 | Source / mirror folder selection | Settings dialog & `--source/--mirror` |
| 2 | Storage allocation simulation (size limit, used-vs-allocated, overflow prevention) | `storage_manager.py` |
| 3 | Real-time file monitoring (create/update/delete/rename) via **watchdog** | `watcher.py` |
| 4 | Smart incremental sync (only changed files, preserves folder structure) | `sync_engine.py` |
| 5 | Background service (runs continuously) + optional **auto-start on login** | `service.py`, `autostart.py` |
| 6 | Recovery mode — "Restore from Mirror" | `sync_engine.restore()` |
| 7 | Versioning — keeps the last *N* (default 3) versions of changed/deleted files | `versioning.py` |
| 8 | Logging system (rotating file logs + live UI feed) | `logger.py` |
| 9 | Performance: queue-based worker, event coalescing, skips identical files | `sync_engine.py` |
| 10 | Clean dashboard (paths, status, storage bar, Start/Pause/Restore/Settings) | `ui/` |
| ✚ | CLI support and system-tray (minimize to tray) | `cli.py`, `ui/app.py` |

### Safety

- The mirror zone is a directory the app manages; user data in the **source** is
  never modified during sync.
- **Restore** never overwrites existing source files unless you explicitly tick
  *"Overwrite existing files"* (UI) or pass `--overwrite` (CLI).
- Permission and I/O errors are caught, logged, and surfaced in the UI without
  crashing the sync loop.
- A persistent "This is NOT real RAID" warning is shown in the UI, the CLI and
  this README.

## Architecture

```
smartmirror/
├── watcher.py          # watchdog observer -> sync events
├── sync_engine.py      # queue-based incremental copy / delete / move / restore
├── storage_manager.py  # allocation + usage accounting + overflow checks
├── versioning.py       # keep last N versions of changed/removed files
├── service.py          # orchestrates watcher + engine + storage (lifecycle)
├── autostart.py        # cross-platform launch-on-login
├── config.py / paths.py# persisted settings + per-OS directories
├── logger.py           # rotating file logs + in-memory buffer for the UI
├── cli.py / __main__.py# command line interface
└── ui/                 # PySide6 dashboard, settings dialog, tray icon
logs/                   # runtime logs (when run from source)
tests/                  # pytest suite (no GUI / display required)
packaging/              # PyInstaller spec for Windows/macOS/Linux builds
```

Data flows: **watchdog** detects a change → a `SyncEvent` is queued → a single
worker thread copies only what changed into the mirror (storing a version first
if the file already existed), enforcing the storage allocation. The UI and CLI
both drive the same `MirrorService`.

> **Why PySide6 instead of Electron?** The brief allowed "PyQt if simpler".
> A pure-Python Qt app keeps the Python backend and UI in one process (no
> Python↔Electron IPC), ships a native tray icon, and packages to a single
> executable per OS with PyInstaller.

## Requirements

- Python **3.9+**
- `watchdog` (file monitoring) and `PySide6` (GUI) — see `requirements.txt`

> 📦 **Detailed, OS-by-OS install instructions (Windows, Linux, macOS) are in
> [INSTALL.md](INSTALL.md)** — including build steps, usage, auto-start, and
> troubleshooting.

## Setup (run from source)

```bash
git clone <repo-url>
cd smartmirror-raid

python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt        # runtime deps
# or for development (tests, lint, build tools):
pip install -r requirements-dev.txt
```

### Launch the desktop UI

```bash
python -m smartmirror            # opens the dashboard
python -m smartmirror tray       # start minimised to the system tray
```

On Linux the GUI needs a display. For a headless/CI environment you can run the
core logic via the CLI (below) or set `QT_QPA_PLATFORM=offscreen` for smoke
tests.

### Command line interface

```bash
# One-off full mirror
python -m smartmirror sync --once --source ~/Documents --mirror /mnt/backup/mirror --size-gb 50

# Continuous mirroring (watches for changes until Ctrl+C)
python -m smartmirror sync --source ~/Documents --mirror /mnt/backup/mirror --size-gb 50

# Show configuration + storage usage
python -m smartmirror status

# Persist configuration / toggle auto-start / versions kept
python -m smartmirror config --source ~/Documents --mirror /mnt/backup/mirror --size-gb 50 --versions 3 --autostart on

# Recovery: copy mirror back to the source (existing files kept unless --overwrite)
python -m smartmirror restore                 # interactive confirmation
python -m smartmirror restore --yes --overwrite
```

Configuration is stored per-user:

| OS | Config | Logs |
|----|--------|------|
| Linux | `~/.config/smartmirror-raid/config.json` | `~/.local/share/smartmirror-raid/logs/` |
| macOS | `~/Library/Application Support/SmartMirror RAID/config.json` | `…/SmartMirror RAID/logs/` |
| Windows | `%APPDATA%\SmartMirror RAID\config.json` | `%LOCALAPPDATA%\SmartMirror RAID\logs\` |

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest                 # headless; no display required
ruff check .           # lint
```

## Building standalone executables

All platforms use the same PyInstaller spec (`packaging/smartmirror.spec`).
Build **on** the target OS (PyInstaller does not cross-compile).

```bash
pip install -r requirements-dev.txt     # includes pyinstaller
pyinstaller packaging/smartmirror.spec
```

### Windows (`.exe`)

```bat
pip install -r requirements-dev.txt
pyinstaller packaging\smartmirror.spec
:: Output: dist\SmartMirrorRAID.exe  (windowed, no console)
```

### macOS (`.app`)

```bash
pip install -r requirements-dev.txt
pyinstaller packaging/smartmirror.spec
# Output: dist/SmartMirrorRAID.app  (and dist/SmartMirrorRAID binary)
# Optional: codesign / notarize for distribution.
```

### Linux

```bash
pip install -r requirements-dev.txt
pyinstaller packaging/smartmirror.spec
# Output: dist/SmartMirrorRAID  (single-file binary)
# Tip: wrap into an AppImage or .deb for distribution if desired.
```

The built binary accepts the same arguments as `python -m smartmirror`, e.g.
`SmartMirrorRAID --tray`.

## Auto-start on boot / login

Enable from **Settings → "Start automatically on login"** or via
`smartmirror config --autostart on`. Implemented natively per OS:

- **Linux** — XDG autostart entry: `~/.config/autostart/smartmirror-raid.desktop`
- **macOS** — LaunchAgent: `~/Library/LaunchAgents/com.smartmirror-raid.plist`
- **Windows** — registry value under `HKCU\…\CurrentVersion\Run`

## License

MIT — see [LICENSE](LICENSE).
