"""SmartMirror RAID.

A cross-platform desktop application that simulates RAID-1 like behaviour on a
single disk using software-level mirroring.

IMPORTANT: This is NOT real RAID. It is a software-based mirroring and backup
system. It does not provide hardware fault tolerance.
"""

from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
