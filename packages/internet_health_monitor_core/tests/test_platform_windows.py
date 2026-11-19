"""Tests for the Windows probes against a fake IP Helper API."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from solentlabs.internet_health_monitor_core.platforms.windows import (
    IP_SUCCESS,
    IP_TTL_EXPIRED_TRANSIT,
    WindowsPlatform,
)

IP_REQ_TIMED_OUT = 11010

# Echo replies by TTL -> traced hops. Replies are (IP_STATUS, address, rtt ms),
# as the API returned them in a real Windows run (2026-11-19).
# fmt: off
TRACE_CASES = [
    ("three routers",
     {1: (IP_TTL_EXPIRED_TRANSIT, "192.168.1.1", 1), 2: (IP_TTL_EXPIRED_TRANSIT, "10.0.0.1", 9),
      3: (IP_TTL_EXPIRED_TRANSIT, "198.51.100.1", 10)},
     {1: "192.168.1.1", 2: "10.0.0.1", 3: "198.51.100.1"}),
    ("silent hop skipped",
     {1: (IP_TTL_EXPIRED_TRANSIT, "192.168.1.1", 1), 2: (IP_REQ_TIMED_OUT, None, None),
      3: (IP_TTL_EXPIRED_TRANSIT, "198.51.100.1", 10)},
     {1: "192.168.1.1", 3: "198.51.100.1"}),
    ("target reached early stops",
     {1: (IP_TTL_EXPIRED_TRANSIT, "192.168.1.1", 1), 2: (IP_SUCCESS, "203.0.113.9", 5)},
     {1: "192.168.1.1", 2: "203.0.113.9"}),
]

# echo reply -> ping result
PING_CASES = [
    ("reply",     (IP_SUCCESS, "192.168.1.1", 2),        (True, 2.0)),
    ("sub-ms",    (IP_SUCCESS, "192.168.1.1", 0),        (True, 0.0)),
    ("timed out", (IP_REQ_TIMED_OUT, None, None),        (False, None)),
]
# fmt: on


@dataclass
class FakeIpHelper:
    """Stands in for _iphlpapi.IpHelper."""

    replies: dict[int, tuple[int, str | None, int | None]] = field(default_factory=dict)
    reply: tuple[int, str | None, int | None] = (IP_SUCCESS, None, None)
    gateway: str | None = "192.168.1.1"
    servers: list[str] = field(default_factory=list)
    error: Exception | None = None
    ttls: list[int] = field(default_factory=list)

    def echo(self, ip: str, ttl: int, timeout_ms: int) -> tuple[int, str | None, int | None]:
        """Return the scripted reply for this TTL."""
        if self.error:
            raise self.error
        self.ttls.append(ttl)
        return self.replies.get(ttl, self.reply)

    def next_hop(self, destination: str) -> str | None:
        """Return the scripted gateway."""
        return self.gateway

    def dns_servers(self) -> list[str]:
        """Return the scripted DNS servers."""
        return self.servers


@pytest.mark.parametrize(("description", "replies", "expected"), TRACE_CASES, ids=[c[0] for c in TRACE_CASES])
async def test_trace(description: str, replies: dict, expected: dict[int, str]) -> None:
    """Each hop is the router whose Time Exceeded answered that TTL."""
    api = FakeIpHelper(replies=replies, reply=(IP_REQ_TIMED_OUT, None, None))
    assert await WindowsPlatform(api).trace("8.8.8.8", 3) == expected


async def test_trace_stops_at_target() -> None:
    """No probes are sent past the hop that reached the target."""
    api = FakeIpHelper(replies=TRACE_CASES[2][1])
    await WindowsPlatform(api).trace("203.0.113.9", 3)
    assert api.ttls == [1, 2]


@pytest.mark.parametrize(("description", "reply", "expected"), PING_CASES, ids=[c[0] for c in PING_CASES])
async def test_ping(description: str, reply: tuple, expected: tuple[bool, float | None]) -> None:
    """Only IP_SUCCESS is a reply; RTT is Windows' whole-millisecond value."""
    assert await WindowsPlatform(FakeIpHelper(reply=reply)).ping("192.168.1.1", 2) == expected


@pytest.mark.parametrize("method", ["ping", "trace"])
async def test_api_error_is_no_reply(method: str) -> None:
    """An OSError from the API counts as no reply."""
    platform = WindowsPlatform(FakeIpHelper(error=OSError("boom")))
    result = await getattr(platform, method)("192.168.1.1", 2 if method == "ping" else 3)
    assert result == ((False, None) if method == "ping" else {})


@pytest.mark.parametrize(("servers", "expected"), [(["192.168.1.1", "1.1.1.1"], "192.168.1.1"), ([], None)])
async def test_system_dns(servers: list[str], expected: str | None) -> None:
    """System DNS is the first configured server."""
    assert await WindowsPlatform(FakeIpHelper(servers=servers)).system_dns() == expected


async def test_default_gateway() -> None:
    """The gateway is the routing table's next hop toward the internet."""
    assert await WindowsPlatform(FakeIpHelper(gateway="192.168.1.1")).default_gateway() == "192.168.1.1"


async def test_host_environment_unknown() -> None:
    """Windows reports unknown host details rather than guessing."""
    env = await WindowsPlatform(FakeIpHelper()).host_environment()
    assert env.connection_type == "unknown"
    assert env.container_type is None
