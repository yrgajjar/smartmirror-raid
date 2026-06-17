"""Single source of truth for the application version."""

from __future__ import annotations

__version__ = "1.0.0"

APP_NAME = "SmartMirror RAID"
APP_ID = "smartmirror-raid"

# A short, always-visible reminder that this tool is not a hardware RAID array.
NOT_REAL_RAID_WARNING = (
    "This is NOT real RAID. SmartMirror RAID performs software-level file "
    "mirroring on a single machine and does not protect against disk failure."
)
