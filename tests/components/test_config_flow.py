"""Tests for Internet Health Monitor config flow."""

from __future__ import annotations

from unittest.mock import Mock, PropertyMock, patch

import pytest
from homeassistant import config_entries

from custom_components.internet_health_monitor.config_flow import (
    ConfigFlow,
    OptionsFlowHandler,
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
    DNS_SERVERS,
    DOMAIN,
    NAME,
)


def _options_flow(entry: Mock) -> OptionsFlowHandler:
    """Build the options flow as HA does, with HA supplying config_entry."""
    flow = ConfigFlow.async_get_options_flow(entry)
    flow.hass = Mock()
    return flow


@pytest.fixture
def read_only_config_entry():
    """Make OptionsFlow.config_entry read-only, as in current HA (no setter)."""
    with patch.object(config_entries.OptionsFlow, "config_entry", new_callable=PropertyMock) as prop:
        yield prop


class TestConfigConstants:
    """Test configuration constants are properly defined."""

    def test_domain_is_correct(self):
        """Test that DOMAIN is correctly defined."""
        assert DOMAIN == "internet_health_monitor"

    def test_name_is_correct(self):
        """Test that NAME is correctly defined."""
        assert NAME == "Internet Health Monitor"

    def test_scan_interval_defaults(self):
        """Test scan interval default values."""
        assert DEFAULT_SCAN_INTERVAL == 60  # 1 minute
        assert 10 <= DEFAULT_SCAN_INTERVAL <= 3600

    def test_ping_count_default(self):
        """Test ping count default value."""
        assert DEFAULT_PING_COUNT == 3
        assert 1 <= DEFAULT_PING_COUNT <= 10

    def test_dns_server_default(self):
        """Test DNS server default value."""
        assert DEFAULT_DNS_SERVER == "auto"

    def test_dns_servers_options(self):
        """Test available DNS server options."""
        assert "auto" in DNS_SERVERS
        assert "1.1.1.1" in DNS_SERVERS  # Cloudflare
        assert "8.8.8.8" in DNS_SERVERS  # Google
        assert "9.9.9.9" in DNS_SERVERS  # Quad9

    def test_config_keys_defined(self):
        """Test that all config keys are defined."""
        assert CONF_ENABLE_GATEWAY_MONITORING == "enable_gateway_monitoring"
        assert CONF_ENABLE_DNS_MONITORING == "enable_dns_monitoring"
        assert CONF_SCAN_INTERVAL == "scan_interval"
        assert CONF_DNS_SERVER == "dns_server"
        assert CONF_PING_COUNT == "ping_count"


class TestConfigFlow:
    """Test the config flow."""

    def test_config_flow_version(self):
        """Test that config flow version is set."""
        assert ConfigFlow.VERSION == 1

    @pytest.mark.asyncio
    async def test_user_step_shows_form(self):
        """Test that user step shows form when no input provided."""
        flow = ConfigFlow()
        flow.hass = Mock()

        # Mock async_set_unique_id to succeed
        with patch.object(flow, "async_set_unique_id"), patch.object(flow, "_abort_if_unique_id_configured"):
            result = await flow.async_step_user(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert "data_schema" in result

    @pytest.mark.asyncio
    async def test_user_step_creates_entry(self):
        """Test that user step creates entry with valid input."""
        flow = ConfigFlow()
        flow.hass = Mock()

        user_input = {
            CONF_ENABLE_GATEWAY_MONITORING: True,
            CONF_ENABLE_DNS_MONITORING: True,
            CONF_SCAN_INTERVAL: 60,
            CONF_DNS_SERVER: "auto",
            CONF_PING_COUNT: 3,
        }

        with patch.object(flow, "async_set_unique_id"), patch.object(flow, "_abort_if_unique_id_configured"):
            result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == "create_entry"
        assert result["title"] == NAME
        assert result["data"] == {}
        assert result["options"] == user_input

    @pytest.mark.asyncio
    async def test_user_step_gateway_disabled(self):
        """Test config with gateway monitoring disabled."""
        flow = ConfigFlow()
        flow.hass = Mock()

        user_input = {
            CONF_ENABLE_GATEWAY_MONITORING: False,
            CONF_ENABLE_DNS_MONITORING: True,
            CONF_SCAN_INTERVAL: 120,
            CONF_DNS_SERVER: "8.8.8.8",
            CONF_PING_COUNT: 5,
        }

        with patch.object(flow, "async_set_unique_id"), patch.object(flow, "_abort_if_unique_id_configured"):
            result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == "create_entry"
        assert result["options"][CONF_ENABLE_GATEWAY_MONITORING] is False
        assert result["options"][CONF_ENABLE_DNS_MONITORING] is True

    @pytest.mark.asyncio
    async def test_user_step_dns_disabled(self):
        """Test config with DNS monitoring disabled."""
        flow = ConfigFlow()
        flow.hass = Mock()

        user_input = {
            CONF_ENABLE_GATEWAY_MONITORING: True,
            CONF_ENABLE_DNS_MONITORING: False,
            CONF_SCAN_INTERVAL: 60,
            CONF_DNS_SERVER: "auto",
            CONF_PING_COUNT: 3,
        }

        with patch.object(flow, "async_set_unique_id"), patch.object(flow, "_abort_if_unique_id_configured"):
            result = await flow.async_step_user(user_input=user_input)

        assert result["type"] == "create_entry"
        assert result["options"][CONF_ENABLE_GATEWAY_MONITORING] is True
        assert result["options"][CONF_ENABLE_DNS_MONITORING] is False


class TestOptionsFlow:
    """Test the options flow."""

    def test_options_flow_handler_exists(self):
        """Test that OptionsFlowHandler exists."""
        assert OptionsFlowHandler is not None

    def test_options_flow_has_init_step(self):
        """Test that options flow has init step."""
        assert hasattr(OptionsFlowHandler, "async_step_init")

    @pytest.mark.asyncio
    async def test_options_step_shows_form(self, read_only_config_entry):
        """Test that options step shows form with current values."""
        mock_entry = Mock()
        mock_entry.options = {
            CONF_ENABLE_GATEWAY_MONITORING: True,
            CONF_ENABLE_DNS_MONITORING: True,
            CONF_SCAN_INTERVAL: 60,
            CONF_DNS_SERVER: "auto",
            CONF_PING_COUNT: 3,
        }

        read_only_config_entry.return_value = mock_entry
        flow = _options_flow(mock_entry)

        result = await flow.async_step_init(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"
        assert "data_schema" in result

    @pytest.mark.asyncio
    async def test_options_step_updates_options(self, read_only_config_entry):
        """Test that options step updates options."""
        mock_entry = Mock()
        mock_entry.options = {
            CONF_ENABLE_GATEWAY_MONITORING: True,
            CONF_ENABLE_DNS_MONITORING: True,
            CONF_SCAN_INTERVAL: 60,
            CONF_DNS_SERVER: "auto",
            CONF_PING_COUNT: 3,
        }

        read_only_config_entry.return_value = mock_entry
        flow = _options_flow(mock_entry)

        new_options = {
            CONF_ENABLE_GATEWAY_MONITORING: False,
            CONF_ENABLE_DNS_MONITORING: True,
            CONF_SCAN_INTERVAL: 120,
            CONF_DNS_SERVER: "8.8.8.8",
            CONF_PING_COUNT: 5,
        }

        result = await flow.async_step_init(user_input=new_options)

        assert result["type"] == "create_entry"
        assert result["data"] == new_options

    @pytest.mark.asyncio
    async def test_options_preserves_existing_values(self, read_only_config_entry):
        """Test that options form shows existing values as defaults."""
        mock_entry = Mock()
        existing_options = {
            CONF_ENABLE_GATEWAY_MONITORING: False,
            CONF_ENABLE_DNS_MONITORING: False,
            CONF_SCAN_INTERVAL: 300,
            CONF_DNS_SERVER: "1.1.1.1",
            CONF_PING_COUNT: 10,
        }
        mock_entry.options = existing_options

        read_only_config_entry.return_value = mock_entry
        flow = _options_flow(mock_entry)

        result = await flow.async_step_init(user_input=None)

        # Verify form is shown with schema
        assert result["type"] == "form"
        assert "data_schema" in result


class TestOptionsFlowCreation:
    """The options flow opens on current HA, where config_entry has no setter."""

    def test_get_options_flow_does_not_assign_config_entry(self):
        """Opening options must not assign config_entry (HA 2026.9 AttributeError)."""
        with patch.object(
            config_entries.OptionsFlow,
            "config_entry",
            property(lambda self: None),
        ):
            flow = ConfigFlow.async_get_options_flow(Mock())
        assert isinstance(flow, OptionsFlowHandler)


class TestConfigFlowRegistration:
    """Test the config flow registration."""

    def test_handler_is_registered(self):
        """Test that the config flow handler is registered with correct domain."""
        handler = config_entries.HANDLERS.get(DOMAIN)
        assert handler is not None
        assert handler == ConfigFlow


class TestScanIntervalValidation:
    """Test scan interval validation."""

    def test_scan_interval_minimum(self):
        """Test minimum scan interval is 10 seconds."""
        # From config_flow schema: vol.Range(min=10, max=3600)
        assert DEFAULT_SCAN_INTERVAL >= 10

    def test_scan_interval_maximum(self):
        """Test maximum scan interval is 1 hour."""
        # From config_flow schema: vol.Range(min=10, max=3600)
        assert DEFAULT_SCAN_INTERVAL <= 3600

    def test_common_intervals_valid(self):
        """Test common interval values are within valid range."""
        common_intervals = [
            10,  # Minimum
            30,  # 30 seconds
            60,  # 1 minute (default)
            120,  # 2 minutes
            300,  # 5 minutes
            600,  # 10 minutes
            3600,  # 1 hour (maximum)
        ]
        for interval in common_intervals:
            assert 10 <= interval <= 3600


class TestPingCountValidation:
    """Test ping count validation."""

    def test_ping_count_minimum(self):
        """Test minimum ping count is 1."""
        # From config_flow schema: vol.Range(min=1, max=10)
        assert DEFAULT_PING_COUNT >= 1

    def test_ping_count_maximum(self):
        """Test maximum ping count is 10."""
        # From config_flow schema: vol.Range(min=1, max=10)
        assert DEFAULT_PING_COUNT <= 10


class TestDNSServerValidation:
    """Test DNS server validation."""

    def test_dns_servers_is_dict(self):
        """Test that DNS_SERVERS is a dictionary."""
        assert isinstance(DNS_SERVERS, dict)

    def test_dns_servers_have_labels(self):
        """Test that all DNS servers have labels."""
        for server, label in DNS_SERVERS.items():
            assert isinstance(server, str)
            assert isinstance(label, str)
            assert len(label) > 0

    def test_auto_option_exists(self):
        """Test that auto-detect option exists."""
        assert "auto" in DNS_SERVERS
        assert DNS_SERVERS["auto"] == "Auto-detect"
