"""Tests for network diagnostics module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from solentlabs.internet_health_monitor_core.network_diagnostics import (
    HopInfo,
    HostEnvironment,
    NetworkDiagnostics,
    NetworkDiagnosticsConfig,
    NetworkDiagnosticsResult,
    _detect_system_dns_sync,
    parse_ping_rtt_ms,
    parse_traceroute_hops,
)

# Ping output -> round-trip time (ms) reported by ping itself.
# Summary formats follow HA core's ping matchers (REFERENCES.md § R10).
# fmt: off
PING_RTT_CASES = [
    # (description, output, expected_ms)
    (
        "iputils summary",
        "PING 192.168.1.1 (192.168.1.1) 56(84) bytes of data.\n"
        "64 bytes from 192.168.1.1: icmp_seq=1 ttl=64 time=0.512 ms\n\n"
        "--- 192.168.1.1 ping statistics ---\n"
        "1 packets transmitted, 1 received, 0% packet loss, time 0ms\n"
        "rtt min/avg/max/mdev = 0.512/0.512/0.512/0.000 ms\n",
        0.512,
    ),
    (
        "busybox summary",
        "PING 192.168.1.1 (192.168.1.1): 56 data bytes\n"
        "64 bytes from 192.168.1.1: seq=0 ttl=64 time=12.345 ms\n\n"
        "--- 192.168.1.1 ping statistics ---\n"
        "1 packets transmitted, 1 packets received, 0% packet loss\n"
        "round-trip min/avg/max = 12.345/12.345/12.345 ms\n",
        12.345,
    ),
    (
        "avg is used, not min or max",
        "rtt min/avg/max/mdev = 1.000/2.500/4.000/1.000 ms\n",
        2.5,
    ),
    (
        "no reply, no summary",
        "1 packets transmitted, 0 received, 100% packet loss, time 0ms\n",
        None,
    ),
    ("empty output", "", None),
]
# fmt: on


# traceroute -n output -> {hop number: IP}, hops 1-3 only.
# fmt: off
TRACEROUTE_CASES = [
    # (description, output, expected)
    (
        "three hops",
        "traceroute to 8.8.8.8 (8.8.8.8), 3 hops max, 46 byte packets\n"
        " 1  192.168.1.1  0.512 ms\n 2  10.0.0.1  8.1 ms\n 3  198.51.100.1  12.0 ms\n",
        {1: "192.168.1.1", 2: "10.0.0.1", 3: "198.51.100.1"},
    ),
    (
        "timeouts skipped",
        " 1  172.19.0.1  0.007 ms\n 2  *\n 3  *\n",
        {1: "172.19.0.1"},
    ),
    (
        "hops past 3 ignored",
        " 1  192.168.1.1  1 ms\n 4  1.2.3.4  20 ms\n",
        {1: "192.168.1.1"},
    ),
    ("IPv6 hop", " 1  fe80::1  0.5 ms\n", {1: "fe80::1"}),
    ("non-IP token skipped", " 1  gateway.lan  0.5 ms\n", {}),
    ("empty output", "", {}),
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


@pytest.mark.parametrize(
    ("description", "output", "expected"),
    TRACEROUTE_CASES,
    ids=[c[0] for c in TRACEROUTE_CASES],
)
def test_parse_traceroute_hops(description: str, output: str, expected: dict[int, str]) -> None:
    """Hop IPs come from numeric traceroute lines, hops 1-3, timeouts skipped."""
    assert parse_traceroute_hops(output) == expected


@pytest.mark.parametrize(
    ("description", "output", "expected"),
    PING_RTT_CASES,
    ids=[c[0] for c in PING_RTT_CASES],
)
def test_parse_ping_rtt_ms(description: str, output: str, expected: float | None) -> None:
    """Round-trip time comes from ping's own summary line."""
    assert parse_ping_rtt_ms(output) == expected


class TestDetectSystemDNS:
    """Tests for DNS detection."""

    def test_detect_dns_from_resolv_conf(self, tmp_path):
        """Test detecting DNS from resolv.conf."""
        resolv_conf = tmp_path / "resolv.conf"
        resolv_conf.write_text("nameserver 8.8.8.8\nnameserver 8.8.4.4\n")

        with patch(
            "solentlabs.internet_health_monitor_core.network_diagnostics.RESOLV_CONF_PATH",
            str(resolv_conf),
        ):
            result = _detect_system_dns_sync()
            assert result == "8.8.8.8"

    def test_detect_dns_no_file(self, tmp_path):
        """Test DNS detection when file doesn't exist."""
        with patch(
            "solentlabs.internet_health_monitor_core.network_diagnostics.RESOLV_CONF_PATH",
            str(tmp_path / "nonexistent"),
        ):
            result = _detect_system_dns_sync()
            assert result is None


class TestNetworkDiagnosticsConfig:
    """Tests for NetworkDiagnosticsConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = NetworkDiagnosticsConfig()
        assert config.ping_count == 3
        assert config.ping_timeout == 2
        assert config.dns_server == "auto"
        assert config.dns_timeout == 5
        assert config.history_size == 30

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

    def test_clear_history(self):
        """Test clearing latency history."""
        diag = NetworkDiagnostics()
        diag._gateway_latency_history.append(10.0)
        diag._gateway_latency_history.append(20.0)
        diag._hop_latency_history[1].append(5.0)
        diag._hop_latency_history[2].append(15.0)
        assert len(diag._gateway_latency_history) == 2
        assert len(diag._hop_latency_history[1]) == 1

        diag.clear_history()
        assert len(diag._gateway_latency_history) == 0
        assert len(diag._hop_latency_history[1]) == 0
        assert len(diag._hop_latency_history[2]) == 0

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
        diag._gateway_latency_history.append(10.0)
        diag._hostnames_collected = True

        diag.reset_all()
        assert diag._gateway_ip is None
        assert diag._hop_ips == {}
        assert len(diag._gateway_latency_history) == 0
        assert diag._hostnames_collected is False

    def test_calculate_jitter_insufficient_data(self):
        """Test jitter calculation with insufficient data."""
        from collections import deque

        diag = NetworkDiagnostics()
        history = deque()
        assert diag._calculate_jitter(history) is None

        history.append(10.0)
        assert diag._calculate_jitter(history) is None  # Need at least 2 samples

    def test_calculate_jitter(self):
        """Test jitter calculation with sufficient data."""
        from collections import deque

        diag = NetworkDiagnostics()
        history = deque([10.0, 12.0, 8.0, 11.0])

        jitter = diag._calculate_jitter(history)
        assert jitter is not None
        assert jitter > 0


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


class TestNetworkDiagnosticsAsync:
    """Async tests for NetworkDiagnostics."""

    @pytest.mark.asyncio
    async def test_detect_gateway(self):
        """Test gateway detection with mocked subprocess."""
        diag = NetworkDiagnostics()

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            b"default via 192.168.1.1 dev eth0",
            b"",
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            gateway = await diag._detect_gateway()
            assert gateway == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_detect_gateway_failure(self):
        """Test gateway detection when command fails."""
        diag = NetworkDiagnostics()

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"error")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            gateway = await diag._detect_gateway()
            assert gateway is None
            assert diag._gateway_detection_failed is True

    @pytest.mark.asyncio
    async def test_single_ping_success(self):
        """Test successful ping."""
        diag = NetworkDiagnostics()

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            b"rtt min/avg/max/mdev = 3.210/3.210/3.210/0.000 ms\n",
            b"",
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            success, latency = await diag._single_ping("192.168.1.1")
            assert success is True
            assert latency == 3.21

    @pytest.mark.asyncio
    async def test_single_ping_reply_without_rtt(self):
        """A reply whose RTT can't be parsed counts as received, with no latency."""
        diag = NetworkDiagnostics()

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"unrecognised output\n", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            success, latency = await diag._single_ping("192.168.1.1")
            assert success is True
            assert latency is None

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
    async def test_single_ping_failure(self):
        """Test failed ping."""
        diag = NetworkDiagnostics()

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            success, latency = await diag._single_ping("192.168.1.1")
            assert success is False
            assert latency is None

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

        with patch(
            "solentlabs.internet_health_monitor_core.network_diagnostics.detect_system_dns",
            return_value="1.1.1.1",
        ):
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
