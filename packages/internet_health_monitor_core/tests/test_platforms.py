"""Tests for the platform factory."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from solentlabs.internet_health_monitor_core.platforms import UnsupportedPlatformError, get_platform
from solentlabs.internet_health_monitor_core.platforms.linux import LinuxPlatform
from solentlabs.internet_health_monitor_core.platforms.windows import WindowsPlatform

# sys.platform value -> platform name
# fmt: off
FACTORY_CASES = [
    ("linux", "linux"),
    ("win32", "windows"),
]
# fmt: on


@pytest.mark.parametrize(("system", "expected"), FACTORY_CASES)
def test_get_platform(system: str, expected: str) -> None:
    """Each supported OS gets its own module."""
    with patch("solentlabs.internet_health_monitor_core.platforms._iphlpapi.IpHelper", create=True):
        assert get_platform(system).name == expected


@pytest.mark.parametrize("system", ["darwin", "freebsd14"])
def test_unsupported_platform(system: str) -> None:
    """Other OSes fail clearly instead of reporting nothing."""
    with pytest.raises(UnsupportedPlatformError, match=system):
        get_platform(system)


def test_platforms_satisfy_interface() -> None:
    """Both modules expose every interface method."""
    for cls in (LinuxPlatform, WindowsPlatform):
        for method in (
            "default_gateway",
            "system_dns",
            "ping",
            "trace",
            "host_environment",
            "missing_tools",
            "missing_optional_tools",
        ):
            assert callable(getattr(cls, method))
