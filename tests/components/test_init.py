"""Tests for Internet Health Monitor integration setup."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from custom_components.internet_health_monitor import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
    async_update_options,
)
from custom_components.internet_health_monitor.const import (
    CONF_DNS_SERVER,
    CONF_ENABLE_DNS_MONITORING,
    CONF_ENABLE_GATEWAY_MONITORING,
    CONF_PING_COUNT,
    CONF_SCAN_INTERVAL,
    DEFAULT_DNS_SERVER,
    DEFAULT_PING_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NAME,
    VERSION,
)


class TestPlatforms:
    """Test platform definitions."""

    def test_platforms_defined(self):
        """Test that platforms list is defined."""
        assert PLATFORMS is not None
        assert isinstance(PLATFORMS, list)

    def test_platforms_contains_expected(self):
        """Test that all expected platforms are defined."""
        assert Platform.BINARY_SENSOR in PLATFORMS
        assert Platform.BUTTON in PLATFORMS
        assert Platform.SENSOR in PLATFORMS

    def test_platforms_count(self):
        """Test expected number of platforms."""
        assert len(PLATFORMS) == 3


class TestConstants:
    """Test integration constants."""

    def test_domain(self):
        """Test DOMAIN constant."""
        assert DOMAIN == "internet_health_monitor"

    def test_name(self):
        """Test NAME constant."""
        assert NAME == "Internet Health Monitor"

    def test_version(self):
        """Test VERSION constant."""
        assert VERSION is not None
        # Version should be semver format
        parts = VERSION.split(".")
        assert len(parts) >= 2

    def test_default_values(self):
        """Test default configuration values."""
        assert DEFAULT_SCAN_INTERVAL == 60
        assert DEFAULT_DNS_SERVER == "auto"
        assert DEFAULT_PING_COUNT == 3


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = Mock(spec=HomeAssistant)
        hass.data = {}
        hass.config_entries = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        return hass

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        entry.options = {
            CONF_SCAN_INTERVAL: 60,
            CONF_DNS_SERVER: "auto",
            CONF_PING_COUNT: 3,
            CONF_ENABLE_GATEWAY_MONITORING: True,
            CONF_ENABLE_DNS_MONITORING: True,
        }
        entry.add_update_listener = Mock(return_value=Mock())
        entry.async_on_unload = Mock()
        return entry

    @pytest.mark.asyncio
    async def test_setup_entry_success(self, mock_hass, mock_entry):
        """Test successful setup entry."""
        mock_result = Mock()
        mock_result.gateway_ip = "192.168.1.1"
        mock_result.gateway_reachable = True
        mock_result.gateway_latency_ms = 5.0
        mock_result.gateway_jitter_ms = 1.0
        mock_result.packet_loss_percent = 0.0
        mock_result.packets_sent = 3
        mock_result.packets_received = 3

        with patch("custom_components.internet_health_monitor.NetworkDiagnostics") as mock_diag_class:
            mock_diag = Mock()
            mock_diag.run_diagnostics = AsyncMock(return_value=mock_result)
            mock_diag_class.return_value = mock_diag

            with patch("custom_components.internet_health_monitor.DataUpdateCoordinator") as mock_coordinator_class:
                mock_coordinator = AsyncMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock()
                mock_coordinator_class.return_value = mock_coordinator

                result = await async_setup_entry(mock_hass, mock_entry)

        assert result is True
        assert DOMAIN in mock_hass.data
        assert mock_entry.entry_id in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_setup_entry_creates_coordinator(self, mock_hass, mock_entry):
        """Test that setup creates coordinator."""
        mock_result = Mock()

        with patch("custom_components.internet_health_monitor.NetworkDiagnostics") as mock_diag_class:
            mock_diag = Mock()
            mock_diag.run_diagnostics = AsyncMock(return_value=mock_result)
            mock_diag_class.return_value = mock_diag

            with patch("custom_components.internet_health_monitor.DataUpdateCoordinator") as mock_coordinator_class:
                mock_coordinator = AsyncMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock()
                mock_coordinator_class.return_value = mock_coordinator

                await async_setup_entry(mock_hass, mock_entry)

                # Verify coordinator was created
                mock_coordinator_class.assert_called_once()
                call_kwargs = mock_coordinator_class.call_args[1]
                assert call_kwargs["name"] == DOMAIN
                assert call_kwargs["update_interval"] == timedelta(seconds=60)

    @pytest.mark.asyncio
    async def test_setup_entry_stores_data(self, mock_hass, mock_entry):
        """Test that setup stores data correctly."""
        mock_result = Mock()

        with patch("custom_components.internet_health_monitor.NetworkDiagnostics") as mock_diag_class:
            mock_diag = Mock()
            mock_diag.run_diagnostics = AsyncMock(return_value=mock_result)
            mock_diag_class.return_value = mock_diag

            with patch("custom_components.internet_health_monitor.DataUpdateCoordinator") as mock_coordinator_class:
                mock_coordinator = AsyncMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock()
                mock_coordinator_class.return_value = mock_coordinator

                await async_setup_entry(mock_hass, mock_entry)

        stored_data = mock_hass.data[DOMAIN][mock_entry.entry_id]
        assert "coordinator" in stored_data
        assert "diagnostics" in stored_data
        assert "config" in stored_data

    @pytest.mark.asyncio
    async def test_setup_entry_config_with_defaults(self, mock_hass):
        """Test setup with default configuration."""
        entry = Mock(spec=ConfigEntry)
        entry.entry_id = "test_entry"
        entry.options = {}  # No options set
        entry.add_update_listener = Mock(return_value=Mock())
        entry.async_on_unload = Mock()

        mock_result = Mock()

        with patch("custom_components.internet_health_monitor.NetworkDiagnostics") as mock_diag_class:
            mock_diag = Mock()
            mock_diag.run_diagnostics = AsyncMock(return_value=mock_result)
            mock_diag_class.return_value = mock_diag

            with patch("custom_components.internet_health_monitor.DataUpdateCoordinator") as mock_coordinator_class:
                mock_coordinator = AsyncMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock()
                mock_coordinator_class.return_value = mock_coordinator

                result = await async_setup_entry(mock_hass, entry)

        assert result is True

    @pytest.mark.asyncio
    async def test_setup_entry_forwards_platforms(self, mock_hass, mock_entry):
        """Test that setup forwards platform setup."""
        mock_result = Mock()

        with patch("custom_components.internet_health_monitor.NetworkDiagnostics") as mock_diag_class:
            mock_diag = Mock()
            mock_diag.run_diagnostics = AsyncMock(return_value=mock_result)
            mock_diag_class.return_value = mock_diag

            with patch("custom_components.internet_health_monitor.DataUpdateCoordinator") as mock_coordinator_class:
                mock_coordinator = AsyncMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock()
                mock_coordinator_class.return_value = mock_coordinator

                await async_setup_entry(mock_hass, mock_entry)

        mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(mock_entry, PLATFORMS)

    @pytest.mark.asyncio
    async def test_setup_entry_registers_update_listener(self, mock_hass, mock_entry):
        """Test that setup registers options update listener."""
        mock_result = Mock()

        with patch("custom_components.internet_health_monitor.NetworkDiagnostics") as mock_diag_class:
            mock_diag = Mock()
            mock_diag.run_diagnostics = AsyncMock(return_value=mock_result)
            mock_diag_class.return_value = mock_diag

            with patch("custom_components.internet_health_monitor.DataUpdateCoordinator") as mock_coordinator_class:
                mock_coordinator = AsyncMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock()
                mock_coordinator_class.return_value = mock_coordinator

                await async_setup_entry(mock_hass, mock_entry)

        mock_entry.async_on_unload.assert_called_once()


class TestAsyncUnloadEntry:
    """Test async_unload_entry function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = Mock(spec=HomeAssistant)
        hass.config_entries = Mock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        return hass

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        return entry

    @pytest.mark.asyncio
    async def test_unload_entry_success(self, mock_hass, mock_entry):
        """Test successful unload entry."""
        mock_hass.data = {
            DOMAIN: {
                mock_entry.entry_id: {
                    "coordinator": Mock(),
                    "diagnostics": Mock(),
                    "config": {},
                }
            }
        }

        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is True
        assert mock_entry.entry_id not in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_unload_entry_removes_data(self, mock_hass, mock_entry):
        """Test that unload removes entry data."""
        mock_hass.data = {
            DOMAIN: {
                mock_entry.entry_id: {"coordinator": Mock()},
                "other_entry": {"coordinator": Mock()},
            }
        }

        await async_unload_entry(mock_hass, mock_entry)

        assert mock_entry.entry_id not in mock_hass.data[DOMAIN]
        assert "other_entry" in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_unload_entry_unloads_platforms(self, mock_hass, mock_entry):
        """Test that unload unloads platforms."""
        mock_hass.data = {DOMAIN: {mock_entry.entry_id: {"coordinator": Mock()}}}

        await async_unload_entry(mock_hass, mock_entry)

        mock_hass.config_entries.async_unload_platforms.assert_called_once_with(mock_entry, PLATFORMS)

    @pytest.mark.asyncio
    async def test_unload_entry_failure(self, mock_hass, mock_entry):
        """Test unload entry when platform unload fails."""
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
        mock_hass.data = {DOMAIN: {mock_entry.entry_id: {"coordinator": Mock()}}}

        result = await async_unload_entry(mock_hass, mock_entry)

        assert result is False
        # Data should still be present since unload failed
        assert mock_entry.entry_id in mock_hass.data[DOMAIN]


class TestAsyncUpdateOptions:
    """Test async_update_options function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = Mock(spec=HomeAssistant)
        hass.config_entries = Mock()
        hass.config_entries.async_reload = AsyncMock()
        return hass

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        return entry

    @pytest.mark.asyncio
    async def test_update_options_reloads_entry(self, mock_hass, mock_entry):
        """Test that options update triggers reload."""
        await async_update_options(mock_hass, mock_entry)

        mock_hass.config_entries.async_reload.assert_called_once_with(mock_entry.entry_id)


class TestMonitoringConfig:
    """Test monitoring configuration handling."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = Mock(spec=HomeAssistant)
        hass.data = {}
        hass.config_entries = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        return hass

    @pytest.mark.asyncio
    async def test_config_stores_monitoring_flags(self, mock_hass):
        """Test that monitoring flags are stored in config."""
        entry = Mock(spec=ConfigEntry)
        entry.entry_id = "test_entry"
        entry.options = {
            CONF_ENABLE_GATEWAY_MONITORING: False,
            CONF_ENABLE_DNS_MONITORING: True,
        }
        entry.add_update_listener = Mock(return_value=Mock())
        entry.async_on_unload = Mock()

        mock_result = Mock()

        with patch("custom_components.internet_health_monitor.NetworkDiagnostics") as mock_diag_class:
            mock_diag = Mock()
            mock_diag.run_diagnostics = AsyncMock(return_value=mock_result)
            mock_diag_class.return_value = mock_diag

            with patch("custom_components.internet_health_monitor.DataUpdateCoordinator") as mock_coordinator_class:
                mock_coordinator = AsyncMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock()
                mock_coordinator_class.return_value = mock_coordinator

                await async_setup_entry(mock_hass, entry)

        stored_config = mock_hass.data[DOMAIN][entry.entry_id]["config"]
        assert stored_config["enable_gateway"] is False
        assert stored_config["enable_dns"] is True
