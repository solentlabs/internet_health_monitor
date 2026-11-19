"""The interface every OS module implements, and the data it returns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class HostEnvironment:
    """Information about the host environment."""

    # Network connection
    connection_type: str = "unknown"  # wifi, ethernet, bridge, veth, unknown
    interface_name: str | None = None

    # Container/virtualization
    container_type: str | None = None  # docker, podman, lxc, None (native)

    # Home Assistant installation type
    ha_install_type: str | None = None  # haos, container, core, supervised

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "connection_type": self.connection_type,
            "interface_name": self.interface_name,
            "container_type": self.container_type,
            "ha_install_type": self.ha_install_type,
        }


class UnsupportedPlatformError(RuntimeError):
    """Raised when no OS module exists for the running platform."""


class Platform(Protocol):
    """OS-specific probes. Everything else in Core is shared across OSes."""

    name: str

    async def default_gateway(self) -> str | None:
        """Return the default gateway IP, or None if there is none."""

    async def system_dns(self) -> str | None:
        """Return the first DNS server the OS is configured to use, or None."""

    async def ping(self, host: str, timeout_s: int) -> tuple[bool, float | None]:
        """Send one echo request; return (reply received, round-trip ms or None)."""

    async def trace(self, target: str, max_hops: int) -> dict[int, str]:
        """Return {hop number: IP} for hops 1 to max_hops; unanswered hops are left out."""

    async def host_environment(self) -> HostEnvironment:
        """Describe the host: connection type, container, install type."""
