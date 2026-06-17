# SmartMirror RAID — Installation Guide

Complete installation and setup instructions for **Windows**, **Linux**, and **macOS**.

> ⚠️ **This is NOT real RAID.** SmartMirror RAID continuously copies files from a
> source folder into a "mirror zone" using software-level replication. It is a
> backup/mirroring tool and does **not** protect against physical disk failure
> (if the disk dies, both copies can be lost). For true hardware redundancy use
> OS/hardware RAID across separate disks.

---

## Table of contents

1. [What you get](#what-you-get)
2. [Prerequisites](#prerequisites)
3. [Get the code](#get-the-code)
4. [Windows](#windows)
5. [Linux](#linux)
6. [macOS](#macos)
7. [First-run / using the app](#first-run--using-the-app)
8. [Command-line interface (CLI)](#command-line-interface-cli)
9. [Auto-start on login](#auto-start-on-login)
10. [Where settings & logs live](#where-settings--logs-live)
11. [Updating](#updating)
12. [Uninstall](#uninstall)
13. [Troubleshooting](#troubleshooting)

---

## What you get

There are two ways to install on every platform:

- **Option A — Run from source.** Fastest; requires Python. Good for trying it
  out and for development.
- **Option B — Build a standalone executable.** Produces a single file
  (`SmartMirrorRAID.exe` / `SmartMirrorRAID` / `SmartMirrorRAID.app`) that runs
  without a separate Python install. Built with PyInstaller.

> PyInstaller does **not** cross-compile — build the executable **on** the OS you
> want to target (build the Windows `.exe` on Windows, the `.app` on macOS, etc.).

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | **3.9 or newer** (3.10+ recommended) | Needed for source + building |
| pip | bundled with Python | Package installer |
| git | any recent | To clone the repo (or download the ZIP) |

Runtime Python dependencies (installed automatically via `requirements.txt`):

- `watchdog` — cross-platform real-time file monitoring
- `PySide6` — the Qt-based desktop UI

---

## Get the code

```bash
git clone https://github.com/tma-it-admin/smartmirror-raid.git
cd smartmirror-raid
```

(Or download the ZIP from the GitHub page and extract it, then `cd` into the
folder.)

---

## Windows

### Option A — Run from source

1. Install **Python 3.10+** from <https://www.python.org/downloads/windows/>.
   During setup, tick **“Add python.exe to PATH”**.
2. Open **PowerShell** (or Command Prompt) in the project folder and run:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python -m smartmirror
   ```

   The dashboard window opens. To start minimized to the system tray instead:

   ```powershell
   python -m smartmirror tray
   ```

   > If `python` is not found, try `py -3` instead (e.g. `py -3 -m venv .venv`).

### Option B — Build a standalone `.exe`

With the virtual environment active:

```powershell
pip install -r requirements-dev.txt
pyinstaller packaging\smartmirror.spec
```

The executable is created at **`dist\SmartMirrorRAID.exe`** — double-click to run,
or launch `dist\SmartMirrorRAID.exe --tray` to start in the tray. You can copy
this `.exe` to any Windows machine; no Python required.

> SmartScreen may warn about an unsigned app the first time — click
> **More info → Run anyway**. Code-sign the binary for wider distribution.

---

## Linux

A desktop environment (X11/Wayland) is required for the GUI. On a headless
server use the [CLI](#command-line-interface-cli).

### Option A — Run from source

1. Ensure Python 3.9+ and `venv` are available. On Debian/Ubuntu:

   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip git
   ```

   On Fedora: `sudo dnf install -y python3 python3-pip git`.
   On Arch: `sudo pacman -S python git`.

2. From the project folder:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python -m smartmirror
   ```

   > Qt may need a few system libraries on minimal installs. On Ubuntu, if the
   > window fails to start, install:
   > ```bash
   > sudo apt install -y libxcb-cursor0 libegl1 libgl1 libxkbcommon0
   > ```

### Option B — Build a standalone binary

```bash
pip install -r requirements-dev.txt
pyinstaller packaging/smartmirror.spec
```

Produces a single-file binary at **`dist/SmartMirrorRAID`**:

```bash
./dist/SmartMirrorRAID            # GUI
./dist/SmartMirrorRAID --tray     # start in tray
./dist/SmartMirrorRAID status     # CLI
```

For distribution you can wrap it into an AppImage or a `.deb`/`.rpm` package.

---

## macOS

### Option A — Run from source

1. Install Python 3.10+ — either from <https://www.python.org/downloads/macos/>
   or via Homebrew:

   ```bash
   brew install python git
   ```

2. From the project folder:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python -m smartmirror
   ```

   The first launch may prompt for permission to access folders (e.g. Desktop,
   Documents) — grant it so mirroring can read those locations.

### Option B — Build a standalone `.app`

```bash
pip install -r requirements-dev.txt
pyinstaller packaging/smartmirror.spec
```

Produces **`dist/SmartMirrorRAID.app`** (and a `dist/SmartMirrorRAID` binary).
Double-click the `.app`, or run it from a terminal:

```bash
open dist/SmartMirrorRAID.app
```

> Because the app is unsigned, Gatekeeper may block the first launch. Either
> **right-click → Open** and confirm, or remove the quarantine attribute:
> ```bash
> xattr -dr com.apple.quarantine dist/SmartMirrorRAID.app
> ```
> For distribution, code-sign and notarize the bundle.

---

## First-run / using the app

1. Click **Settings**.
2. Set:
   - **Source folder** — what you want protected (e.g. `C:\Users\You\Documents`,
     `/home/you/Documents`, `/Users/you/Documents`).
   - **Mirror folder** — where the copy lives (e.g. another drive/partition such
     as `D:\Backup\mirror`, `/mnt/backup/mirror`, `/Volumes/Backup/mirror`).
   - **Mirror size (allocation)** — the storage budget (e.g. 50 GiB). The app
     tracks usage and refuses to exceed it.
   - Optional: **versioning** (keep last N versions), **hash verification**, and
     **start on login**.
3. Click **OK**, then **Start Sync**. Existing files are mirrored once, then
   changes are mirrored in real time.
4. **Restore from Mirror** copies the mirror back to the source. Existing source
   files are never overwritten unless you tick **“Overwrite existing files”**.
5. Closing the window minimizes to the **system tray** (if available); use the
   tray menu to show the dashboard, pause/resume, or quit.

---

## Command-line interface (CLI)

Useful for servers, automation, or headless machines. Replace `python -m smartmirror`
with the built binary name (e.g. `SmartMirrorRAID`) if you built Option B.

```bash
# One-off full mirror
python -m smartmirror sync --once --source <SRC> --mirror <DST> --size-gb 50

# Continuous mirroring (watches for changes until Ctrl+C)
python -m smartmirror sync --source <SRC> --mirror <DST> --size-gb 50

# Show configuration + storage usage
python -m smartmirror status

# Save configuration / toggle options
python -m smartmirror config --source <SRC> --mirror <DST> --size-gb 50 \
    --versions 3 --autostart on

# Recovery: copy mirror back to the source
python -m smartmirror restore                 # asks for confirmation
python -m smartmirror restore --yes --overwrite
```

---

## Auto-start on login

Enable from **Settings → “Start automatically on login”** or with
`smartmirror config --autostart on`. Implemented natively per OS:

| OS | Mechanism |
|----|-----------|
| Windows | Registry value under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
| macOS | LaunchAgent at `~/Library/LaunchAgents/com.smartmirror-raid.plist` |
| Linux | XDG autostart entry at `~/.config/autostart/smartmirror-raid.desktop` |

Disable it again from Settings or with `--autostart off`.

---

## Where settings & logs live

| OS | Config file | Logs |
|----|-------------|------|
| Windows | `%APPDATA%\SmartMirror RAID\config.json` | `%LOCALAPPDATA%\SmartMirror RAID\logs\` |
| macOS | `~/Library/Application Support/SmartMirror RAID/config.json` | `…/SmartMirror RAID/logs/` |
| Linux | `~/.config/smartmirror-raid/config.json` | `~/.local/share/smartmirror-raid/logs/` |

---

## Updating

```bash
cd smartmirror-raid
git pull
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Rebuild the executable (Option B) afterwards if you use the standalone build.

---

## Uninstall

- Delete the project folder (and the `dist/` build output, if any).
- Remove the per-user config/log folders listed above.
- If you enabled auto-start, disable it first (`smartmirror config --autostart off`)
  or delete the autostart entry for your OS from the table above.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `python` not found (Windows) | Use `py -3 …`, or reinstall Python with **“Add to PATH”** ticked. |
| GUI won’t open on Linux | Install Qt libs: `sudo apt install -y libxcb-cursor0 libegl1 libgl1 libxkbcommon0`. On headless servers, use the CLI. |
| macOS “app is damaged / unidentified developer” | `xattr -dr com.apple.quarantine dist/SmartMirrorRAID.app`, or right-click → Open. |
| “Mirror zone is full” in the log | Increase **Mirror size** in Settings, or free disk space — the app refuses to exceed the allocation. |
| Permission errors during sync | Run with an account that can read the source and write the mirror; errors are logged and skipped without crashing. |
| Nothing syncs after Start | Confirm Source and Mirror are set, different, and the Source exists (see **Settings**), then check the activity log. |
| Want a clean test | Point Source/Mirror at empty temp folders first to watch it work before mirroring real data. |

Still stuck? Open an issue on the repository with the relevant lines from the log
file (paths above).
