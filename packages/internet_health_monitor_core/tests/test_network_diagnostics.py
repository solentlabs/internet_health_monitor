"""Tests for network diagnostics module."""

from __future__ import annotations

import socket
from unittest.mock import AsyncMock, patch

import pytest

from solentlabs.internet_health_monitor_core.network_diagnostics import (
    HopInfo,
    HostEnvironment,
    NetworkDiagnostics,
    NetworkDiagnosticsConfig,
    NetworkDiagnosticsResult,
    consecutive_jitter,
    format_ms,
)

# Round-trip times in sending order -> jitter: mean |difference| of consecutive
# samples (RFC 3550 consecutive form, Cloudflare's speed test; ADR-009).
# fmt: off
JITTER_CASES = [
    ("steady",            [5.0, 5.0, 5.0],       0.0),
    ("one swing",         [1.0, 3.0, 2.0],       1.5),
    ("order matters",     [1.0, 2.0, 3.0],       1.0),  # same values, spread smaller than the swing above
    ("two samples",       [10.0, 14.0],          4.0),
    ("one sample",        [10.0],                None),
    ("no replies",        [],                    None),
]
# fmt: on


@pytest.mark.parametrize(("description", "rtts", "expected"), JITTER_CASES, ids=[c[0] for c in JITTER_CASES])
def test_consecutive_jitter(description: str, rtts: list[float], expected: float | None) -> None:
    """Jitter is the mean absolute change between consecutive round-trip times."""
    assert consecutive_jitter(rtts) == expected


# Log value -> text. A missing measurement shows as "n/a", never 0.0ms.
# fmt: off
FORMAT_MS_CASES = [
    ("value",   1.234, "1.2ms"),
    ("zero",    0.0,   "0.0ms"),
    ("missing", None,  "n/a"),
]

# gethostbyaddr result (or exception) -> hostname IHM keeps
REVERSE_DNS_CASES = [
    ("name found",           ("router.example.com", [], ["192.0.2.1"]), "router.example.com"),
    ("resolver echoes IP",   ("192.0.2.1", [], ["192.0.2.1"]),          None),
    ("no PTR record",        socket.herror(1, "Unknown host"),          None),
]
# fmt: on

# Reverse DNS result per hop -> cached hostnames. Lookups that find no name
# or raise are left out.
# fmt: off
HOSTNAME_CASES = [
    # (description, lookup results by IP, expected hostnames)
    ("names found", {"192.168.1.1": "router.lan", "198.51.100.1": "isp.example.net"},
     {1: "router.lan", 2: "isp.example.net"}),
    ("no PTR record", {"192.168.1.1": None, "198.51.100.1": "isp.example.net"},
     {2: "isp.example.net"}),
    ("lookup raises", {"192.168.1.1": OSError("boom"), "198.51.100.1": None}, {}),
]
# fmt: on


class TestNetworkDiagnosticsConfig:
    """Tests for NetworkDiagnosticsConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = NetworkDiagnosticsConfig()
        assert config.ping_count == 3
        assert config.ping_timeout == 2
        assert config.dns_server == "auto"
        assert config.dns_timeout == 5

    def test_custom_config(self):
        """Test custom configuration values."""
        config = NetworkDiagnosticsConfig(
            ping_count=5,
            dns_server="8.8.8.8",
        )
        assert config.ping_count == 5
        assert config.dns_server == "8.8.8.8"


class TestNetworkDiagnostics:
    """Tests for NetworkDiagnostics class."""

    def test_init_default(self):
        """Test default initialization."""
        diag = NetworkDiagnostics()
        assert diag.config.ping_count == 3
        assert diag.config.dns_server == "auto"

    def test_init_with_overrides(self):
        """Test initialization with parameter overrides."""
        diag = NetworkDiagnostics(dns_server="8.8.8.8", ping_count=5)
        assert diag.config.dns_server == "8.8.8.8"
        assert diag.config.ping_count == 5

    def test_reset_gateway(self):
        """Test resetting cached gateway."""
        diag = NetworkDiagnostics()
        diag._gateway_ip = "192.168.1.1"
        diag._gateway_detection_failed = True

        diag.reset_gateway()
        assert diag._gateway_ip is None
        assert diag._gateway_detection_failed is False

    def test_reset_all(self):
        """Test resetting all cached data."""
        diag = NetworkDiagnostics()
        diag._gateway_ip = "192.168.1.1"
        diag._hop_ips = {1: "192.168.1.1", 2: "10.0.0.1"}
        diag._hostnames_collected = True

        diag.reset_all()
        assert diag._gateway_ip is None
        assert diag._hop_ips == {}
        assert diag._hostnames_collected is False


class TestNetworkDiagnosticsResult:
    """Tests for NetworkDiagnosticsResult."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = NetworkDiagnosticsResult(
            timestamp=1234567890.0,
            gateway_ip="192.168.1.1",
            gateway_reachable=True,
            gateway_latency_ms=5.5,
            gateway_jitter_ms=1.2,
            packet_loss_percent=0.0,
            packets_sent=3,
            packets_received=3,
            hops=[
                HopInfo(
                    hop_number=1,
                    ip="192.168.1.1",
                    latency_ms=1.0,
                    jitter_ms=0.2,
                    packet_loss_percent=0.0,
                    packets_sent=3,
                    packets_received=3,
                    reachable=True,
                ),
                HopInfo(
                    hop_number=2,
                    ip="10.0.0.1",
                    latency_ms=15.0,
                    jitter_ms=2.0,
                    packet_loss_percent=0.0,
                    packets_sent=3,
                    packets_received=3,
                    reachable=True,
                ),
                HopInfo(
                    hop_number=3,
                    ip="8.8.8.1",
                    latency_ms=20.0,
                    jitter_ms=1.5,
                    packet_loss_percent=0.0,
                    packets_sent=3,
                    packets_received=3,
                    reachable=True,
                ),
            ],
            dns_server="1.1.1.1",
            dns_success=True,
            dns_latency_ms=25.0,
            host_environment=HostEnvironment(connection_type="ethernet", interface_name="eth0"),
            trace_target="8.8.8.8",
        )

        data = result.to_dict()
        assert data["gateway_ip"] == "192.168.1.1"
        assert data["gateway_reachable"] is True
        assert data["gateway_latency_ms"] == 5.5
        assert data["dns_server"] == "1.1.1.1"
        assert len(data["hops"]) == 3
        assert data["trace_target"] == "8.8.8.8"

    def test_legacy_isp_properties(self):
        """Test legacy ISP properties for backwards compatibility."""
        result = NetworkDiagnosticsResult(
            timestamp=1234567890.0,
            gateway_ip="192.168.1.1",
            gateway_reachable=True,
            gateway_latency_ms=5.5,
            gateway_jitter_ms=1.2,
            packet_loss_percent=0.0,
            packets_sent=3,
            packets_received=3,
            hops=[
                HopInfo(
                    hop_number=1,
                    ip="192.168.1.1",
                    latency_ms=1.0,
                    jitter_ms=0.2,
                    packet_loss_percent=0.0,
                    packets_sent=3,
                    packets_received=3,
                    reachable=True,
                ),
                HopInfo(
                    hop_number=2,
                    ip="10.0.0.1",
                    latency_ms=15.0,
                    jitter_ms=2.0,
                    packet_loss_percent=0.0,
                    packets_sent=3,
                    packets_received=3,
                    reachable=True,
                ),
                HopInfo(
                    hop_number=3,
                    ip="8.8.8.1",
                    latency_ms=20.0,
                    jitter_ms=1.5,
                    packet_loss_percent=0.0,
                    packets_sent=3,
                    packets_received=3,
                    reachable=True,
                ),
            ],
            dns_server="1.1.1.1",
            dns_success=True,
            dns_latency_ms=25.0,
        )

        # Legacy properties should return hop 2 data
        assert result.isp_hop_ip == "10.0.0.1"
        assert result.isp_hop_reachable is True
        assert result.isp_hop_latency_ms == 15.0


@pytest.mark.parametrize(
    ("description", "lookups", "expected"),
    HOSTNAME_CASES,
    ids=[c[0] for c in HOSTNAME_CASES],
)
@pytest.mark.asyncio
async def test_collect_hostnames(
    description: str, lookups: dict[str, str | None | Exception], expected: dict[int, str]
) -> None:
    """Hop hostnames come only from reverse DNS; failures leave no entry."""
    diag = NetworkDiagnostics()
    diag._hop_ips = {1: "192.168.1.1", 2: "198.51.100.1"}

    async def fake_lookup(ip: str) -> str | None:
        result = lookups[ip]
        if isinstance(result, Exception):
            raise result
        return result

    with patch.object(diag, "_reverse_dns_lookup", side_effect=fake_lookup):
        await diag._collect_hostnames()

    assert diag._hop_hostnames == expected


@pytest.mark.parametrize(("description", "value", "expected"), FORMAT_MS_CASES, ids=[c[0] for c in FORMAT_MS_CASES])
def test_format_ms(description: str, value: float | None, expected: str) -> None:
    """Summary log shows missing values as n/a."""
    assert format_ms(value) == expected


@pytest.mark.parametrize(
    ("description", "lookup", "expected"), REVERSE_DNS_CASES, ids=[c[0] for c in REVERSE_DNS_CASES]
)
async def test_reverse_dns_lookup(
    description: str, lookup: tuple[str, list[str], list[str]] | Exception, expected: str | None
) -> None:
    """Only a real name counts; an echoed IP or a failed lookup gives None."""
    target = "solentlabs.internet_health_monitor_core.network_diagnostics.socket.gethostbyaddr"
    kwargs = {"side_effect": lookup} if isinstance(lookup, Exception) else {"return_value": lookup}
    with patch(target, **kwargs):
        assert await NetworkDiagnostics()._reverse_dns_lookup("192.0.2.1") == expected


class TestNetworkDiagnosticsAsync:
    """Async tests for NetworkDiagnostics."""

    @pytest.mark.asyncio
    async def test_check_gateway_counts_reply_without_rtt(self):
        """Packet loss counts replies even when their RTT can't be parsed."""
        diag = NetworkDiagnostics(ping_count=2)
        diag._gateway_ip = "192.168.1.1"

        with patch.object(diag, "_single_ping", AsyncMock(side_effect=[(True, None), (True, 4.0)])):
            result = await diag._check_gateway()
        assert result["packets_received"] == 2
        assert result["latency_ms"] == 4.0

    @pytest.mark.asyncio
    async def test_check_single_hop_counts_reply_without_rtt(self):
        """Hop packet loss counts replies even when their RTT can't be parsed."""
        diag = NetworkDiagnostics(ping_count=2)

        with patch.object(diag, "_single_ping", AsyncMock(side_effect=[(True, None), (True, 6.0)])):
            hop = await diag._check_single_hop(2, "203.0.113.1")
        assert hop.packets_received == 2
        assert hop.packet_loss_percent == 0
        assert hop.latency_ms == 6.0

    @pytest.mark.asyncio
    async def test_check_gateway_no_ip(self):
        """Test gateway check when no gateway detected."""
        diag = NetworkDiagnostics()
        diag._gateway_ip = None

        result = await diag._check_gateway()
        assert result["reachable"] is False
        assert result["packets_sent"] == 0

    @pytest.mark.asyncio
    async def test_resolve_dns_server_configured(self):
        """Test DNS resolution with configured server."""
        diag = NetworkDiagnostics(dns_server="8.8.8.8")

        dns = await diag._resolve_dns_server()
        assert dns == "8.8.8.8"

    @pytest.mark.asyncio
    async def test_resolve_dns_server_auto(self):
        """Test DNS resolution with auto detection."""
        diag = NetworkDiagnostics(dns_server="auto")

        with patch.object(diag._platform, "system_dns", AsyncMock(return_value="1.1.1.1")):
            dns = await diag._resolve_dns_server()
            assert dns == "1.1.1.1"

    @pytest.mark.asyncio
    async def test_resolve_trace_target_public_dns(self):
        """Test trace target uses public DNS server."""
        diag = NetworkDiagnostics(dns_server="8.8.8.8")
        diag._dns_server = "8.8.8.8"

        target = diag._resolve_trace_target()
        assert target == "8.8.8.8"

    @pytest.mark.asyncio
    async def test_resolve_trace_target_private_dns(self):
        """Test trace target falls back when DNS is private."""
        diag = NetworkDiagnostics(dns_server="192.168.1.1")
        diag._dns_server = "192.168.1.1"

        target = diag._resolve_trace_target()
        assert target == "8.8.8.8"  # Falls back to default


class TestHopInfo:
    """Tests for HopInfo dataclass."""

    def test_typical_location_gateway(self):
        """Test typical location for hop 1."""
        hop = HopInfo(hop_number=1, ip="192.168.1.1", latency_ms=1.0, reachable=True)
        assert hop.typical_location == "gateway"

    def test_typical_location_isp(self):
        """Test typical location for hop 2."""
        hop = HopInfo(hop_number=2, ip="10.0.0.1", latency_ms=15.0, reachable=True)
        assert hop.typical_location == "isp"

    def test_typical_location_backbone(self):
        """Test typical location for hop 3."""
        hop = HopInfo(hop_number=3, ip="8.8.8.1", latency_ms=20.0, reachable=True)
        assert hop.typical_location == "backbone"

    def test_to_dict(self):
        """Test HopInfo to_dict method."""
        hop = HopInfo(hop_number=2, ip="10.0.0.1", latency_ms=15.0, jitter_ms=2.0, reachable=True)
        data = hop.to_dict()
        assert data["hop_number"] == 2
        assert data["ip"] == "10.0.0.1"
        assert data["latency_ms"] == 15.0
        assert data["jitter_ms"] == 2.0
        assert data["reachable"] is True
        assert data["typical_location"] == "isp"


class TestHostEnvironment:
    """Tests for HostEnvironment dataclass."""

    def test_default_values(self):
        """Test default values."""
        env = HostEnvironment()
        assert env.connection_type == "unknown"
        assert env.interface_name is None
        assert env.container_type is None
        assert env.ha_install_type is None

    def test_custom_values(self):
        """Test custom values."""
        env = HostEnvironment(
            connection_type="ethernet",
            interface_name="eth0",
            container_type="docker",
            ha_install_type="container",
        )
        assert env.connection_type == "ethernet"
        assert env.interface_name == "eth0"
        assert env.container_type == "docker"
        assert env.ha_install_type == "container"

    def test_to_dict(self):
        """Test to_dict method."""
        env = HostEnvironment(connection_type="wifi", interface_name="wlan0")
        data = env.to_dict()
        assert data["connection_type"] == "wifi"
        assert data["interface_name"] == "wlan0"


class FakePlatform:
    """Scripted OS probes for whole-poll tests."""

    name = "fake"

    def __init__(
        self,
        gateway: str | None = "192.168.1.1",
        hops: dict[int, str] | None = None,
        rtt: dict[str, float | None] | None = None,
        dns: str | None = "192.168.1.1",
    ) -> None:
        """Script the answers; hosts missing from rtt do not reply."""
        self.gateway = gateway
        self.hops = {1: "192.168.1.1", 2: "10.0.0.1", 3: "198.51.100.1"} if hops is None else hops
        self.rtt = {"192.168.1.1": 1.0, "10.0.0.1": 8.0, "198.51.100.1": 12.0} if rtt is None else rtt
        self.dns = dns
        self.trace_calls = 0

    async def default_gateway(self) -> str | None:
        """Return the scripted gateway."""
        return self.gateway

    async def system_dns(self) -> str | None:
        """Return the scripted DNS server."""
        return self.dns

    async def ping(self, host: str, timeout_s: int) -> tuple[bool, float | None]:
        """Reply with the scripted RTT, or not at all."""
        return (True, self.rtt[host]) if host in self.rtt else (False, None)

    async def trace(self, target: str, max_hops: int) -> dict[int, str]:
        """Return the scripted hops."""
        self.trace_calls += 1
        return self.hops

    async def host_environment(self) -> HostEnvironment:
        """Return a fixed environment."""
        return HostEnvironment(connection_type="ethernet", interface_name="eth0")

    def missing_tools(self) -> list[str]:
        """Nothing missing."""
        return []

    def missing_optional_tools(self) -> list[str]:
        """Nothing missing."""
        return []


# Scripted platform -> what one poll reports
# fmt: off
POLL_CASES = [
    # (description, platform kwargs, gateway reachable, hop latencies, gateway loss %)
    ("all answer",        {},                                        True,  [1.0, 8.0, 12.0], 0.0),
    ("hop 3 silent",      {"rtt": {"192.168.1.1": 1.0, "10.0.0.1": 8.0}},
                                                                     True,  [1.0, 8.0, None], 0.0),
    ("gateway down",      {"rtt": {}},                               False, [None, None, None], 100.0),
    ("only hop 1 traced", {"hops": {1: "192.168.1.1"}},              True,  [1.0, None, None], 0.0),
    ("no gateway",        {"gateway": None},                         False, [], None),
]
# fmt: on


def _diag(**kwargs: object) -> NetworkDiagnostics:
    """NetworkDiagnostics on a fake platform, with DNS timing stubbed out."""
    diag = NetworkDiagnostics(ping_count=2, platform=FakePlatform(**kwargs))  # type: ignore[arg-type]
    diag._check_dns = AsyncMock(return_value={"success": True, "latency_ms": 20.0})  # type: ignore[method-assign]
    diag._reverse_dns_lookup = AsyncMock(return_value=None)  # type: ignore[method-assign]
    return diag


@pytest.mark.parametrize(
    ("description", "kwargs", "reachable", "hop_latencies", "loss"), POLL_CASES, ids=[c[0] for c in POLL_CASES]
)
async def test_poll(
    description: str, kwargs: dict, reachable: bool, hop_latencies: list[float | None], loss: float | None
) -> None:
    """One poll reports each target's own measurement; missing ones are None."""
    result = await _diag(**kwargs).run_diagnostics()

    assert result.gateway_reachable is reachable
    assert [h.latency_ms for h in result.hops] == hop_latencies
    assert result.packet_loss_percent == loss
    assert result.dns_latency_ms == 20.0
    assert result.host_environment is not None
    assert result.host_environment.interface_name == "eth0"


async def test_detection_is_cached_until_reset() -> None:
    """Hops are traced once, then again only after a cache reset."""
    diag = _diag()
    platform = diag._platform
    await diag.run_diagnostics()
    await diag.run_diagnostics()
    assert platform.trace_calls == 1  # type: ignore[attr-defined]

    diag.reset_all()
    await diag.run_diagnostics()
    assert platform.trace_calls == 2  # type: ignore[attr-defined]


async def test_jitter_from_one_poll() -> None:
    """Jitter comes from the poll's own consecutive pings; no history is needed."""
    diag = _diag()
    diag._gateway_ip = "192.168.1.1"
    diag.config.ping_count = 3
    rtts = iter([1.0, 3.0, 2.0])
    diag._single_ping = AsyncMock(side_effect=lambda host: (True, next(rtts)))  # type: ignore[method-assign]
    result = await diag._check_gateway()
    assert result["jitter_ms"] == 1.5  # (|3-1| + |2-3|) / 2


async def test_auto_dns_falls_back_when_undetected() -> None:
    """With no system DNS found, the fallback server is used and traced toward."""
    diag = _diag(dns=None)
    result = await diag.run_diagnostics()
    assert result.dns_server == "1.1.1.1"
    assert result.trace_target == "1.1.1.1"


# DNS probe outcome -> DNS check result
# fmt: off
DNS_CHECK_CASES = [
    ("answered",       {"return_value": 23.5},                 {"success": True,  "latency_ms": 23.5}),
    ("no answer",      {"return_value": None},                 {"success": False, "latency_ms": None}),
    ("socket error",   {"side_effect": OSError("unreachable")}, {"success": False, "latency_ms": None}),
    ("bad server",     {"side_effect": ValueError("not an IP")}, {"success": False, "latency_ms": None}),
]
# fmt: on


@pytest.mark.parametrize(("description", "probe", "expected"), DNS_CHECK_CASES, ids=[c[0] for c in DNS_CHECK_CASES])
async def test_check_dns(description: str, probe: dict, expected: dict) -> None:
    """DNS latency is one timed query to the server under test, on every OS."""
    diag = NetworkDiagnostics(dns_server="1.1.1.1", platform=FakePlatform())  # type: ignore[arg-type]
    diag._dns_server = "1.1.1.1"
    with patch(
        "solentlabs.internet_health_monitor_core.network_diagnostics.dns_probe.query_time_ms", AsyncMock(**probe)
    ) as query:
        assert await diag._check_dns() == expected
    assert query.await_args.args[0] == "1.1.1.1"


# hop_ownership setting -> lookups made and owner fields on hop 3
# fmt: off
OWNERSHIP_CASES = [
    ("off by default", False, 0, (None, None)),
    ("on",             True,  3, (64500, "EXAMPLE-NET")),
]
# fmt: on


@pytest.mark.parametrize(
    ("description", "enabled", "lookups", "hop3_owner"), OWNERSHIP_CASES, ids=[c[0] for c in OWNERSHIP_CASES]
)
async def test_hop_ownership_opt_in(
    description: str, enabled: bool, lookups: int, hop3_owner: tuple[int | None, str | None]
) -> None:
    """Owners are looked up only when enabled, once per detection, via the DNS server under test."""
    from solentlabs.internet_health_monitor_core.hop_owner import HopOwner

    async def fake_lookup(ip: str, server: str, timeout_s: float) -> HopOwner | None:
        assert server == "192.168.1.1"
        return HopOwner(64500, "EXAMPLE-NET") if ip == "198.51.100.1" else None

    diag = _diag()
    diag.config.hop_ownership = enabled
    with patch(
        "solentlabs.internet_health_monitor_core.network_diagnostics.lookup_owner", side_effect=fake_lookup
    ) as lookup:
        await diag.run_diagnostics()
        result = await diag.run_diagnostics()

    assert lookup.call_count == lookups
    hop3 = result.get_hop(3)
    assert hop3 is not None
    assert (hop3.asn, hop3.as_name) == hop3_owner
    assert hop3.to_dict()["asn"] == hop3_owner[0]


async def test_owner_lookup_error_leaves_hop_unowned() -> None:
    """A failing lookup never breaks the poll."""
    diag = _diag()
    diag.config.hop_ownership = True
    with patch("solentlabs.internet_health_monitor_core.network_diagnostics.lookup_owner", side_effect=OSError("down")):
        result = await diag.run_diagnostics()
    assert all(h.asn is None for h in result.hops)


async def test_detection_state_reports_cache() -> None:
    """detection_state shows what a poll detected, for the diagnostics download."""
    diag = _diag()
    await diag.run_diagnostics()
    state = diag.detection_state()
    assert state["platform"] == "fake"
    assert state["hop_detection_failed"] is False
    assert state["trace_target"] == "8.8.8.8"
