"""The interface every OS module implements, and the data it returns."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any, Literal, Protocol

# Read from the default route's interface name; in a container without host
# networking it is the container's own interface (README.md § Known Limitations).
ConnectionType = Literal["ethernet", "wifi", "bridge", "veth", "unknown"]


@dataclass
class HostEnvironment:
    """Information about the host environment."""

    # Network connection
    connection_type: ConnectionType = "unknown"
    interface_name: str | None = None

    # Container/virtualization
    container_type: str | None = None  # docker, podman, lxc, None (native)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "connection_type": self.connection_type,
            "interface_name": self.interface_name,
            "container_type": self.container_type,
        }


def is_ip(value: str) -> bool:
    """Whether *value* is a literal IPv4 or IPv6 address: the only thing a probe may target."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


class UnsupportedPlatformError(RuntimeError):
    """Raised when no OS module exists for the running platform."""


class Platform(Protocol):
    """OS-specific probes. Everything else in Core is shared across OSes."""

    name: str

    async def default_gateway(self) -> str | None:
        """Return the default gateway IP, or None if there is none."""
        ...

    async def system_dns(self) -> str | None:
        """Return the first DNS server the OS is configured to use, or None."""
        ...

    async def ping(self, host: str, timeout_s: int) -> tuple[bool, float | None]:
        """Send one echo request; return (reply received, round-trip ms or None)."""
        ...

    async def trace(self, target: str, max_hops: int) -> dict[int, str]:
        """Return {hop number: IP} for hops 1 to max_hops; unanswered hops are left out."""
        ...

    async def host_environment(self) -> HostEnvironment:
        """Describe the host: connection type and container."""
        ...

    def missing_tools(self) -> list[str]:
        """Return required system tools that are not installed (blocking: run in an executor)."""
        ...

    def missing_optional_tools(self) -> list[str]:
        """Return optional tools that are not installed; each disables part of the measurements."""
        ...
