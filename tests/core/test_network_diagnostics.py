"""Tests for network diagnostics module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.ha_internet_health_monitor.core.network_diagnostics import (
    NetworkDiagnostics,
    NetworkDiagnosticsConfig,
    NetworkDiagnosticsResult,
    _detect_system_dns_sync,
)


class TestDetectSystemDNS:
    """Tests for DNS detection."""

    def test_detect_dns_from_resolv_conf(self, tmp_path):
        """Test detecting DNS from resolv.conf."""
        resolv_conf = tmp_path / "resolv.conf"
        resolv_conf.write_text("nameserver 8.8.8.8\nnameserver 8.8.4.4\n")

        with patch(
            "custom_components.ha_internet_health_monitor.core.network_diagnostics.RESOLV_CONF_PATH",
            str(resolv_conf),
        ):
            result = _detect_system_dns_sync()
            assert result == "8.8.8.8"

    def test_detect_dns_no_file(self, tmp_path):
        """Test DNS detection when file doesn't exist."""
        with patch(
            "custom_components.ha_internet_health_monitor.core.network_diagnostics.RESOLV_CONF_PATH",
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
        diag._latency_history.append(10.0)
        diag._latency_history.append(20.0)
        assert len(diag._latency_history) == 2

        diag.clear_history()
        assert len(diag._latency_history) == 0

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
        diag._isp_hop_ip = "10.0.0.1"
        diag._latency_history.append(10.0)

        diag.reset_all()
        assert diag._gateway_ip is None
        assert diag._isp_hop_ip is None
        assert len(diag._latency_history) == 0

    def test_calculate_jitter_insufficient_data(self):
        """Test jitter calculation with insufficient data."""
        diag = NetworkDiagnostics()
        assert diag._calculate_jitter() is None

        diag._latency_history.append(10.0)
        assert diag._calculate_jitter() is None  # Need at least 2 samples

    def test_calculate_jitter(self):
        """Test jitter calculation with sufficient data."""
        diag = NetworkDiagnostics()
        diag._latency_history.extend([10.0, 12.0, 8.0, 11.0])

        jitter = diag._calculate_jitter()
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
            isp_hop_ip="10.0.0.1",
            isp_hop_reachable=True,
            isp_hop_latency_ms=15.3,
            dns_server="1.1.1.1",
            dns_success=True,
            dns_latency_ms=25.0,
        )

        data = result.to_dict()
        assert data["gateway_ip"] == "192.168.1.1"
        assert data["gateway_reachable"] is True
        assert data["gateway_latency_ms"] == 5.5
        assert data["dns_server"] == "1.1.1.1"


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
        mock_process.communicate.return_value = (b"", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            success, latency = await diag._single_ping("192.168.1.1")
            assert success is True
            assert latency is not None
            assert latency > 0

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
            "custom_components.ha_internet_health_monitor.core.network_diagnostics.detect_system_dns",
            return_value="1.1.1.1",
        ):
            dns = await diag._resolve_dns_server()
            assert dns == "1.1.1.1"
