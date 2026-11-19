"""OS-specific probes behind one interface. `get_platform()` picks the module.

Adding an OS: write a module implementing `Platform` (base.py) and add a
branch below (ARCHITECTURE_DECISIONS.md § ADR-005).
"""

from __future__ import annotations

import sys

from .base import HostEnvironment, Platform, UnsupportedPlatformError

__all__ = ["HostEnvironment", "Platform", "UnsupportedPlatformError", "get_platform"]


def get_platform(system: str = sys.platform) -> Platform:
    """Return the probes for this OS, or raise UnsupportedPlatformError."""
    if system.startswith("linux"):
        from .linux import LinuxPlatform

        return LinuxPlatform()
    if system == "win32":
        from .windows import WindowsPlatform

        return WindowsPlatform()
    raise UnsupportedPlatformError(f"Internet Health Monitor Core does not support {system!r} (Linux and Windows only)")
