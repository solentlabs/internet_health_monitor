"""Outside values never become command options or plain-HTTP load targets (ROADMAP Phase 5 security review)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from solentlabs.internet_health_monitor_core.backends import librespeed, ndt7
from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics, NetworkDiagnosticsConfig
from solentlabs.internet_health_monitor_core.platforms import linux
from solentlabs.internet_health_monitor_core.platforms.linux import (
    LinuxPlatform,
    parse_default_route,
    parse_resolv_conf,
    parse_traceroute_hops,
)
from solentlabs.internet_health_monitor_core.speed_test import SpeedTestError, Transfer

# ┌──────────────────────────────┬──────────────────────────────────────────┐
# │ target                       │ why it must never reach ping/traceroute  │
# ├──────────────────────────────┼──────────────────────────────────────────┤
# │ -oProxyCommand=x             │ would be read as an option               │
# │ --help                       │ option                                   │
# │ example.com                  │ a name, not an address (resolves later)  │
# │ 1.2.3.4; rm -rf /            │ shell-looking text                       │
# │ fe80::1:-x                   │ contains ":" but is not IPv6             │
# └──────────────────────────────┴──────────────────────────────────────────┘
# fmt: off
BAD_TARGETS: list[str] = [
    "-oProxyCommand=x",
    "--help",
    "example.com",
    "1.2.3.4; rm -rf /",
    "fe80::1:-x",
]
# fmt: on


@pytest.mark.parametrize("target", BAD_TARGETS)
async def test_probes_refuse_non_addresses(target: str) -> None:
    """ping and traceroute run only for a literal IP address; anything else is never executed."""
    run = AsyncMock()
    with patch.object(linux, "_run", run):
        assert await LinuxPlatform().ping(target, 2) == (False, None)
        assert await LinuxPlatform().trace(target, 3) == {}
    run.assert_not_called()


# ┌───────────────────────────────────────────────────────┬────────────────────┐
# │ tool output                                           │ parsed             │
# ├───────────────────────────────────────────────────────┼────────────────────┤
# │ default via -x dev eth0                               │ gateway None       │
# │ 1  -oFoo  1.0 ms                                      │ no hop             │
# │ 1  fe80::1:-x  1.0 ms                                 │ no hop             │
# │ nameserver --help                                     │ no server          │
# │ default via 2001:db8::1 dev eth0                      │ IPv6 kept          │
# └───────────────────────────────────────────────────────┴────────────────────┘
def test_parsers_keep_only_addresses() -> None:
    """Tool output that is not an address is dropped by every parser."""
    assert parse_default_route("default via -x dev eth0") == (None, "eth0")
    assert parse_traceroute_hops(" 1  -oFoo  1.0 ms\n 2  fe80::1:-x  1.0 ms", 3) == {}
    assert parse_resolv_conf("nameserver --help\n") is None
    assert parse_default_route("default via 2001:db8::1 dev eth0") == ("2001:db8::1", "eth0")


async def test_configured_dns_server_must_be_an_address() -> None:
    """A stored or typed DNS server that is not an IP falls back instead of reaching traceroute."""
    diagnostics = NetworkDiagnostics(config=NetworkDiagnosticsConfig(dns_server="--help"))
    assert await diagnostics._resolve_dns_server() == "1.1.1.1"


# ┌──────────────────────────────────────────────┬──────────────────────────┐
# │ provider-supplied URL                        │ used                     │
# ├──────────────────────────────────────────────┼──────────────────────────┤
# │ LibreSpeed server http://192.168.1.1/admin   │ no: plain HTTP           │
# │ LibreSpeed server //speed.example.com        │ yes: becomes https       │
# │ M-Lab ws://192.168.1.1/x                     │ no: plain WebSocket      │
# └──────────────────────────────────────────────┴──────────────────────────┘
def test_librespeed_skips_plain_http_servers() -> None:
    """A tampered server list cannot point the load at a LAN device over plain HTTP."""
    entry = {"server": "http://192.168.1.1/admin", "dlURL": "x", "ulURL": "x", "pingURL": "x"}
    assert librespeed.usable(entry, require_tls=True) is False
    assert librespeed.usable({**entry, "server": "//speed.example.com"}, require_tls=True) is True


async def test_ndt7_refuses_plain_websocket() -> None:
    """M-Lab targets must be wss://; anything else is refused before connecting."""
    backend = ndt7.Ndt7Backend("https://locate.example.com")
    candidate = {"machine": "m", "urls": {ndt7.DOWNLOAD_KEY: "ws://192.168.1.1/x", ndt7.UPLOAD_KEY: "ws://x"}}
    with (
        patch.object(backend, "_locate_servers", AsyncMock(return_value=[candidate])),
        pytest.raises(SpeedTestError, match="no M-Lab server could be reached"),
    ):
        async with aiohttp.ClientSession() as session:
            await backend.run(session, 1000, Transfer())
