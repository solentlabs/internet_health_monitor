"""Tests for Internet Health Monitor binary sensor platform."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.internet_health_monitor.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    DNS_BINARY_SENSORS,
    GATEWAY_BINARY_SENSORS,
    InternetHealthBinarySensor,
    async_setup_entry,
)
from custom_components.internet_health_monitor.const import DOMAIN, MANUFACTURER, NAME
from custom_components.internet_health_monitor.core.network_diagnostics import (
    HopInfo,
    HostEnvironment,
    NetworkDiagnosticsResult,
)


def make_result(**overrides) -> NetworkDiagnosticsResult:
    """Create a NetworkDiagnosticsResult with defaults."""
    defaults = {
        "timestamp": 1234567890.0,
        "gateway_ip": "192.168.1.1",
        "gateway_reachable": True,
        "gateway_latency_ms": 5.5,
        "gateway_jitter_ms": 1.2,
        "packet_loss_percent": 0.0,
        "packets_sent": 3,
        "packets_received": 3,
        "dns_server": "1.1.1.1",
        "dns_success": True,
        "dns_latency_ms": 25.0,
        "hops": [
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
        "host_environment": HostEnvironment(connection_type="ethernet", interface_name="eth0"),
        "trace_target": "8.8.8.8",
    }
    defaults.update(overrides)
    return NetworkDiagnosticsResult(**defaults)


class TestBinarySensorDescriptions:
    """Test binary sensor entity descriptions."""

    def test_binary_sensor_descriptions_count(self):
        """Test that all expected binary sensors are defined."""
        # Should have: gateway_reachable, internet_reachable
        assert len(BINARY_SENSOR_DESCRIPTIONS) == 2

    def test_all_sensors_have_keys(self):
        """Test that all sensors have unique keys."""
        keys = [desc.key for desc in BINARY_SENSOR_DESCRIPTIONS]
        assert len(keys) == len(set(keys))  # All unique

    def test_all_sensors_have_translation_keys(self):
        """Test that all sensors have translation keys."""
        for desc in BINARY_SENSOR_DESCRIPTIONS:
            assert desc.translation_key is not None
            assert len(desc.translation_key) > 0

    def test_all_sensors_have_names(self):
        """Test that all sensors have names."""
        for desc in BINARY_SENSOR_DESCRIPTIONS:
            assert desc.name is not None
            assert len(desc.name) > 0

    def test_all_sensors_have_value_functions(self):
        """Test that all sensors have value functions."""
        for desc in BINARY_SENSOR_DESCRIPTIONS:
            assert desc.value_fn is not None
            assert callable(desc.value_fn)

    def test_all_sensors_have_connectivity_device_class(self):
        """Test that all sensors use connectivity device class."""
        for desc in BINARY_SENSOR_DESCRIPTIONS:
            assert desc.device_class == BinarySensorDeviceClass.CONNECTIVITY


class TestGatewayReachableSensor:
    """Test gateway reachable binary sensor description."""

    @pytest.fixture
    def sensor_desc(self):
        """Get gateway reachable sensor description."""
        return next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "gateway_reachable")

    def test_key(self, sensor_desc):
        """Test sensor key."""
        assert sensor_desc.key == "gateway_reachable"

    def test_name(self, sensor_desc):
        """Test sensor name."""
        assert sensor_desc.name == "Gateway Reachable"

    def test_device_class(self, sensor_desc):
        """Test sensor device class."""
        assert sensor_desc.device_class == BinarySensorDeviceClass.CONNECTIVITY

    def test_icon(self, sensor_desc):
        """Test sensor icon."""
        assert sensor_desc.icon == "mdi:lan-check"

    def test_value_function_true(self, sensor_desc):
        """Test value function returns True when gateway reachable."""
        result = make_result(gateway_reachable=True)
        assert sensor_desc.value_fn(result) is True

    def test_value_function_false(self, sensor_desc):
        """Test value function returns False when gateway unreachable."""
        result = make_result(gateway_reachable=False)
        assert sensor_desc.value_fn(result) is False


class TestInternetReachableSensor:
    """Test internet reachable binary sensor description."""

    @pytest.fixture
    def sensor_desc(self):
        """Get internet reachable sensor description."""
        return next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "internet_reachable")

    def test_key(self, sensor_desc):
        """Test sensor key."""
        assert sensor_desc.key == "internet_reachable"

    def test_name(self, sensor_desc):
        """Test sensor name."""
        assert sensor_desc.name == "Internet Reachable"

    def test_device_class(self, sensor_desc):
        """Test sensor device class."""
        assert sensor_desc.device_class == BinarySensorDeviceClass.CONNECTIVITY

    def test_icon(self, sensor_desc):
        """Test sensor icon."""
        assert sensor_desc.icon == "mdi:web-check"

    def test_value_function_true(self, sensor_desc):
        """Test value function returns True when DNS succeeds."""
        result = make_result(dns_success=True)
        assert sensor_desc.value_fn(result) is True

    def test_value_function_false(self, sensor_desc):
        """Test value function returns False when DNS fails."""
        result = make_result(dns_success=False)
        assert sensor_desc.value_fn(result) is False


class TestBinarySensorSets:
    """Test binary sensor categorization sets."""

    def test_gateway_binary_sensors_set(self):
        """Test gateway binary sensors set."""
        assert {"gateway_reachable"} == GATEWAY_BINARY_SENSORS

    def test_dns_binary_sensors_set(self):
        """Test DNS binary sensors set."""
        assert {"internet_reachable"} == DNS_BINARY_SENSORS

    def test_all_sensors_categorized(self):
        """Test that all sensors are categorized."""
        all_keys = {desc.key for desc in BINARY_SENSOR_DESCRIPTIONS}
        categorized = GATEWAY_BINARY_SENSORS | DNS_BINARY_SENSORS
        assert all_keys == categorized


class TestInternetHealthBinarySensor:
    """Test InternetHealthBinarySensor entity."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with sample data."""
        coordinator = Mock()
        coordinator.data = make_result()
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry_id"
        return entry

    @pytest.fixture
    def sensor_desc(self):
        """Get a sensor description for testing."""
        return next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "gateway_reachable")

    def test_sensor_initialization(self, mock_coordinator, mock_entry, sensor_desc):
        """Test sensor initialization."""
        sensor = InternetHealthBinarySensor(mock_coordinator, mock_entry, sensor_desc)

        assert sensor.entity_description == sensor_desc
        assert sensor._attr_unique_id == "test_entry_id_gateway_reachable"

    def test_sensor_device_info(self, mock_coordinator, mock_entry, sensor_desc):
        """Test sensor device info."""
        sensor = InternetHealthBinarySensor(mock_coordinator, mock_entry, sensor_desc)

        assert sensor._attr_device_info["identifiers"] == {(DOMAIN, "test_entry_id")}
        assert sensor._attr_device_info["name"] == NAME
        assert sensor._attr_device_info["manufacturer"] == MANUFACTURER
        assert sensor._attr_device_info["model"] == NAME

    def test_sensor_is_on_true(self, mock_coordinator, mock_entry, sensor_desc):
        """Test sensor is_on returns True when gateway reachable."""
        sensor = InternetHealthBinarySensor(mock_coordinator, mock_entry, sensor_desc)

        assert sensor.is_on is True

    def test_sensor_is_on_false(self, mock_entry, sensor_desc):
        """Test sensor is_on returns False when gateway unreachable."""
        coordinator = Mock()
        coordinator.data = make_result(gateway_reachable=False)

        sensor = InternetHealthBinarySensor(coordinator, mock_entry, sensor_desc)

        assert sensor.is_on is False

    def test_sensor_is_on_no_data(self, mock_entry, sensor_desc):
        """Test sensor is_on returns None when no data."""
        coordinator = Mock()
        coordinator.data = None

        sensor = InternetHealthBinarySensor(coordinator, mock_entry, sensor_desc)

        assert sensor.is_on is None

    def test_has_entity_name(self, mock_coordinator, mock_entry, sensor_desc):
        """Test that sensor has entity name attribute."""
        sensor = InternetHealthBinarySensor(mock_coordinator, mock_entry, sensor_desc)

        assert sensor._attr_has_entity_name is True


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        return Mock()

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        return entry

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator."""
        coordinator = Mock()
        coordinator.data = make_result()
        return coordinator

    @pytest.mark.asyncio
    async def test_setup_all_binary_sensors(self, mock_hass, mock_entry, mock_coordinator):
        """Test setup creates all binary sensors when both monitoring types enabled."""
        mock_hass.data = {
            DOMAIN: {
                mock_entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "config": {"enable_gateway": True, "enable_dns": True},
                }
            }
        }

        added_entities = []

        def capture_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, capture_entities)

        # Should have both binary sensors
        assert len(added_entities) == 2

        keys = {e.entity_description.key for e in added_entities}
        assert keys == {"gateway_reachable", "internet_reachable"}

    @pytest.mark.asyncio
    async def test_setup_gateway_only(self, mock_hass, mock_entry, mock_coordinator):
        """Test setup creates only gateway binary sensor when DNS disabled."""
        mock_hass.data = {
            DOMAIN: {
                mock_entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "config": {"enable_gateway": True, "enable_dns": False},
                }
            }
        }

        added_entities = []

        def capture_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, capture_entities)

        # Should have only gateway binary sensor
        assert len(added_entities) == 1

        keys = {e.entity_description.key for e in added_entities}
        assert keys == {"gateway_reachable"}

    @pytest.mark.asyncio
    async def test_setup_dns_only(self, mock_hass, mock_entry, mock_coordinator):
        """Test setup creates only internet binary sensor when gateway disabled."""
        mock_hass.data = {
            DOMAIN: {
                mock_entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "config": {"enable_gateway": False, "enable_dns": True},
                }
            }
        }

        added_entities = []

        def capture_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, capture_entities)

        # Should have only internet binary sensor
        assert len(added_entities) == 1

        keys = {e.entity_description.key for e in added_entities}
        assert keys == {"internet_reachable"}

    @pytest.mark.asyncio
    async def test_setup_no_binary_sensors(self, mock_hass, mock_entry, mock_coordinator):
        """Test setup creates no binary sensors when both disabled."""
        mock_hass.data = {
            DOMAIN: {
                mock_entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "config": {"enable_gateway": False, "enable_dns": False},
                }
            }
        }

        added_entities = []

        def capture_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(mock_hass, mock_entry, capture_entities)

        # Should have no binary sensors
        assert len(added_entities) == 0
