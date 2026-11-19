"""Windows probes through the IP Helper API: no text parsing, any display language."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Protocol, TypeVar

from .base import HostEnvironment

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")

# IP_STATUS codes (docs/REFERENCES.md § R13)
IP_SUCCESS = 0
IP_TTL_EXPIRED_TRANSIT = 11013

# Any public address works: GetBestRoute only reads the routing table.
ROUTE_PROBE_ADDRESS = "8.8.8.8"
TRACE_TIMEOUT_MS = 2000
DEFAULT_TTL = 128


class IpHelperApi(Protocol):
    """The three IP Helper calls the probes need (real one: _iphlpapi.IpHelper)."""

    def echo(self, ip: str, ttl: int, timeout_ms: int) -> tuple[int, str | None, int | None]:
        """Send one echo request; return (IP_STATUS, replying address, round-trip ms)."""

    def next_hop(self, destination: str) -> str | None:
        """Return the next hop toward destination, or None if on-link."""

    def dns_servers(self) -> list[str]:
        """Return the configured DNS servers."""


class WindowsPlatform:
    """Probes for Windows. Round-trip times are whole milliseconds (R13)."""

    name = "windows"

    def __init__(self, api: IpHelperApi | None = None) -> None:
        """Use the given API, or load iphlpapi.dll."""
        if api is None:
            from ._iphlpapi import IpHelper

            api = IpHelper()
        self._api = api

    async def _call(self, func: Callable[..., _T], *args: object) -> _T:
        """Run a blocking API call in a worker thread."""
        return await asyncio.get_running_loop().run_in_executor(None, func, *args)

    async def default_gateway(self) -> str | None:
        """Return the next hop the routing table uses for the internet."""
        gateway = await self._call(self._api.next_hop, ROUTE_PROBE_ADDRESS)
        _LOGGER.debug("Detected gateway: %s", gateway)
        return gateway

    async def system_dns(self) -> str | None:
        """Return the first configured DNS server."""
        servers = await self._call(self._api.dns_servers)
        _LOGGER.debug("Detected system DNS servers: %s", servers)
        return servers[0] if servers else None

    async def ping(self, host: str, timeout_s: int) -> tuple[bool, float | None]:
        """Send one echo request; latency is the round-trip time Windows reports."""
        try:
            status, _, rtt = await self._call(self._api.echo, host, DEFAULT_TTL, timeout_s * 1000)
        except OSError as e:
            _LOGGER.debug("Ping error for %s: %s", host, e)
            return False, None
        if status != IP_SUCCESS:
            return False, None
        return True, None if rtt is None else float(rtt)

    async def trace(self, target: str, max_hops: int) -> dict[int, str]:
        """Send echo requests with TTL 1..max_hops; each hop is the router that answers."""
        hops: dict[int, str] = {}
        for ttl in range(1, max_hops + 1):
            try:
                status, address, _ = await self._call(self._api.echo, target, ttl, TRACE_TIMEOUT_MS)
            except OSError as e:
                _LOGGER.debug("Trace error at hop %d: %s", ttl, e)
                continue
            if status in (IP_TTL_EXPIRED_TRANSIT, IP_SUCCESS) and address:
                hops[ttl] = address
                _LOGGER.debug("Detected hop %d: %s", ttl, address)
                if status == IP_SUCCESS:
                    break  # reached the target
            else:
                _LOGGER.debug("Hop %d timed out (status %d)", ttl, status)
        return hops

    async def host_environment(self) -> HostEnvironment:
        """Not detected on Windows: every field reports unknown."""
        return HostEnvironment()
