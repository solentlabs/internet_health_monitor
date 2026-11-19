"""Tests for Internet Health Monitor sensor platform."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTime

from custom_components.internet_health_monitor.const import DOMAIN, MANUFACTURER, NAME
from custom_components.internet_health_monitor.sensor import (
    DNS_SENSOR,
    HopJitterSensor,
    HopLatencySensor,
    HopPacketLossSensor,
    InternetHealthSensor,
    async_setup_entry,
)
from solentlabs.internet_health_monitor_core.network_diagnostics import (
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
                packet_loss_percent=10.0,
                packets_sent=3,
                packets_received=2,
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


class TestDNSSensor:
    """Test DNS sensor description."""

    def test_key(self):
        """Test sensor key."""
        assert DNS_SENSOR.key == "dns_latency"

    def test_name(self):
        """Test sensor name."""
        assert DNS_SENSOR.name == "DNS Latency"

    def test_device_class(self):
        """Test sensor device class."""
        assert DNS_SENSOR.device_class == SensorDeviceClass.DURATION

    def test_state_class(self):
        """Test sensor state class."""
        assert DNS_SENSOR.state_class == SensorStateClass.MEASUREMENT

    def test_unit_of_measurement(self):
        """Test sensor unit of measurement."""
        assert DNS_SENSOR.native_unit_of_measurement == UnitOfTime.MILLISECONDS

    def test_value_function(self):
        """Test value function extracts correct data."""
        result = make_result(dns_latency_ms=25.0)
        assert DNS_SENSOR.value_fn(result) == 25.0

    def test_extra_attrs_function(self):
        """Test extra attributes function."""
        result = make_result(dns_server="1.1.1.1", dns_success=True)
        attrs = DNS_SENSOR.extra_attrs_fn(result)
        assert attrs["dns_server"] == "1.1.1.1"
        assert attrs["success"] is True


class TestHopLatencySensor:
    """Test hop latency sensor."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with sample data."""
        coordinator = Mock()
        coordinator.data = make_result()
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry_id"
        return entry

    def test_hop_1_sensor_name(self, mock_coordinator, mock_entry):
        """Test hop 1 sensor has correct name."""
        sensor = HopLatencySensor(mock_coordinator, mock_entry, 1)
        assert sensor._attr_name == "Hop 1 Latency (Gateway)"

    def test_hop_2_sensor_name(self, mock_coordinator, mock_entry):
        """Test hop 2 sensor has correct name."""
        sensor = HopLatencySensor(mock_coordinator, mock_entry, 2)
        assert sensor._attr_name == "Hop 2 Latency (ISP)"

    def test_hop_3_sensor_name(self, mock_coordinator, mock_entry):
        """Test hop 3 sensor has correct name."""
        sensor = HopLatencySensor(mock_coordinator, mock_entry, 3)
        assert sensor._attr_name == "Hop 3 Latency (Backbone)"

    def test_hop_sensor_unique_id(self, mock_coordinator, mock_entry):
        """Test hop sensor has correct unique ID."""
        sensor = HopLatencySensor(mock_coordinator, mock_entry, 2)
        assert sensor._attr_unique_id == "test_entry_id_hop_2_latency"

    def test_hop_sensor_value(self, mock_coordinator, mock_entry):
        """Test hop sensor returns correct latency."""
        sensor = HopLatencySensor(mock_coordinator, mock_entry, 2)
        assert sensor.native_value == 15.0  # hop 2 latency

    def test_hop_sensor_device_class(self, mock_coordinator, mock_entry):
        """Test hop sensor device class."""
        sensor = HopLatencySensor(mock_coordinator, mock_entry, 1)
        assert sensor._attr_device_class == SensorDeviceClass.DURATION

    def test_hop_sensor_unit(self, mock_coordinator, mock_entry):
        """Test hop sensor unit of measurement."""
        sensor = HopLatencySensor(mock_coordinator, mock_entry, 1)
        assert sensor._attr_native_unit_of_measurement == UnitOfTime.MILLISECONDS

    def test_hop_sensor_extra_attrs(self, mock_coordinator, mock_entry):
        """Test hop sensor extra attributes."""
        sensor = HopLatencySensor(mock_coordinator, mock_entry, 2)
        attrs = sensor.extra_state_attributes
        assert attrs["hop_number"] == 2
        assert attrs["hop_ip"] == "10.0.0.1"
        assert attrs["reachable"] is True
        assert attrs["typical_location"] == "isp"

    def test_hop_sensor_with_hostname(self, mock_coordinator, mock_entry):
        """Hop sensor exposes the reverse DNS name as an attribute."""
        hop = HopInfo(
            hop_number=2,
            ip="10.0.0.1",
            latency_ms=15.0,
            jitter_ms=2.0,
            packet_loss_percent=0.0,
            packets_sent=3,
            packets_received=3,
            reachable=True,
            hostname="isp-router.example.com",
        )
        result = make_result(
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
                hop,
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
            ]
        )
        mock_coordinator.data = result

        sensor = HopLatencySensor(mock_coordinator, mock_entry, 2)
        attrs = sensor.extra_state_attributes
        assert attrs["hostname"] == "isp-router.example.com"
        assert "isp" not in attrs
        assert "asn" not in attrs  # only present when hop ownership found an owner

    def test_hop_sensor_with_owner(self, mock_coordinator, mock_entry):
        """With hop ownership on, the owner's ASN and name are attributes."""
        hop = HopInfo(
            hop_number=3, ip="198.51.100.1", latency_ms=12.0, reachable=True, asn=64500, as_name="EXAMPLE-NET"
        )
        mock_coordinator.data = make_result(hops=[hop])
        attrs = HopLatencySensor(mock_coordinator, mock_entry, 3).extra_state_attributes
        assert (attrs["asn"], attrs["as_name"]) == (64500, "EXAMPLE-NET")


class TestHopJitterSensor:
    """Test hop jitter sensor."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with sample data."""
        coordinator = Mock()
        coordinator.data = make_result()
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry_id"
        return entry

    def test_hop_1_sensor_name(self, mock_coordinator, mock_entry):
        """Test hop 1 jitter sensor has correct name."""
        sensor = HopJitterSensor(mock_coordinator, mock_entry, 1)
        assert sensor._attr_name == "Hop 1 Jitter (Gateway)"

    def test_hop_2_sensor_name(self, mock_coordinator, mock_entry):
        """Test hop 2 jitter sensor has correct name."""
        sensor = HopJitterSensor(mock_coordinator, mock_entry, 2)
        assert sensor._attr_name == "Hop 2 Jitter (ISP)"

    def test_hop_3_sensor_name(self, mock_coordinator, mock_entry):
        """Test hop 3 jitter sensor has correct name."""
        sensor = HopJitterSensor(mock_coordinator, mock_entry, 3)
        assert sensor._attr_name == "Hop 3 Jitter (Backbone)"

    def test_hop_sensor_unique_id(self, mock_coordinator, mock_entry):
        """Test hop jitter sensor has correct unique ID."""
        sensor = HopJitterSensor(mock_coordinator, mock_entry, 2)
        assert sensor._attr_unique_id == "test_entry_id_hop_2_jitter"

    def test_hop_sensor_value(self, mock_coordinator, mock_entry):
        """Test hop jitter sensor returns correct value."""
        sensor = HopJitterSensor(mock_coordinator, mock_entry, 2)
        assert sensor.native_value == 2.0  # hop 2 jitter

    def test_hop_sensor_device_class(self, mock_coordinator, mock_entry):
        """Test hop jitter sensor device class."""
        sensor = HopJitterSensor(mock_coordinator, mock_entry, 1)
        assert sensor._attr_device_class == SensorDeviceClass.DURATION

    def test_hop_sensor_unit(self, mock_coordinator, mock_entry):
        """Test hop jitter sensor unit of measurement."""
        sensor = HopJitterSensor(mock_coordinator, mock_entry, 1)
        assert sensor._attr_native_unit_of_measurement == UnitOfTime.MILLISECONDS

    def test_hop_sensor_icon(self, mock_coordinator, mock_entry):
        """Test hop jitter sensor icon."""
        sensor = HopJitterSensor(mock_coordinator, mock_entry, 1)
        assert sensor._attr_icon == "mdi:chart-timeline-variant"


class TestHopPacketLossSensor:
    """Test hop packet loss sensor."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create mock coordinator with sample data."""
        coordinator = Mock()
        coordinator.data = make_result()
        coordinator.last_update_success = True
        return coordinator

    @pytest.fixture
    def mock_entry(self):
        """Create mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry_id"
        return entry

    def test_hop_1_sensor_name(self, mock_coordinator, mock_entry):
        """Test hop 1 packet loss sensor has correct name."""
        sensor = HopPacketLossSensor(mock_coordinator, mock_entry, 1)
        assert sensor._attr_name == "Hop 1 Packet Loss (Gateway)"

    def test_hop_2_sensor_name(self, mock_coordinator, mock_entry):
        """Test hop 2 packet loss sensor has correct name."""
        sensor = HopPacketLossSensor(mock_coordinator, mock_entry, 2)
        assert sensor._attr_name == "Hop 2 Packet Loss (ISP)"

    def test_hop_3_sensor_name(self, mock_coordinator, mock_entry):
        """Test hop 3 packet loss sensor has correct name."""
        sensor = HopPacketLossSensor(mock_coordinator, mock_entry, 3)
        assert sensor._attr_name == "Hop 3 Packet Loss (Backbone)"

    def test_hop_sensor_unique_id(self, mock_coordinator, mock_entry):
        """Test hop packet loss sensor has correct unique ID."""
        sensor = HopPacketLossSensor(mock_coordinator, mock_entry, 2)
        assert sensor._attr_unique_id == "test_entry_id_hop_2_packet_loss"

    def test_hop_sensor_value(self, mock_coordinator, mock_entry):
        """Test hop packet loss sensor returns correct value."""
        sensor = HopPacketLossSensor(mock_coordinator, mock_entry, 2)
        assert sensor.native_value == 10.0  # hop 2 has 10% packet loss

    def test_hop_sensor_unit(self, mock_coordinator, mock_entry):
        """Test hop packet loss sensor unit of measurement."""
        sensor = HopPacketLossSensor(mock_coordinator, mock_entry, 1)
        assert sensor._attr_native_unit_of_measurement == PERCENTAGE

    def test_hop_sensor_icon(self, mock_coordinator, mock_entry):
        """Test hop packet loss sensor icon."""
        sensor = HopPacketLossSensor(mock_coordinator, mock_entry, 1)
        assert sensor._attr_icon == "mdi:network-off"

    def test_hop_sensor_extra_attrs(self, mock_coordinator, mock_entry):
        """Test hop packet loss sensor extra attributes include packet counts."""
        sensor = HopPacketLossSensor(mock_coordinator, mock_entry, 2)
        attrs = sensor.extra_state_attributes
        assert attrs["packets_sent"] == 3
        assert attrs["packets_received"] == 2


class TestInternetHealthSensor:
    """Test InternetHealthSensor entity (used for DNS sensor)."""

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

    def test_sensor_initialization(self, mock_coordinator, mock_entry):
        """Test sensor initialization."""
        sensor = InternetHealthSensor(mock_coordinator, mock_entry, DNS_SENSOR)

        assert sensor.entity_description == DNS_SENSOR
        assert sensor._attr_unique_id == "test_entry_id_dns_latency"

    def test_sensor_device_info(self, mock_coordinator, mock_entry):
        """Test sensor device info."""
        sensor = InternetHealthSensor(mock_coordinator, mock_entry, DNS_SENSOR)

        assert sensor._attr_device_info["identifiers"] == {(DOMAIN, "test_entry_id")}
        assert sensor._attr_device_info["name"] == NAME
        assert sensor._attr_device_info["manufacturer"] == MANUFACTURER
        assert sensor._attr_device_info["model"] == NAME

    def test_sensor_native_value(self, mock_coordinator, mock_entry):
        """Test sensor native value."""
        sensor = InternetHealthSensor(mock_coordinator, mock_entry, DNS_SENSOR)

        assert sensor.native_value == 25.0

    def test_sensor_native_value_no_data(self, mock_entry):
        """Test sensor native value when no data."""
        coordinator = Mock()
        coordinator.data = None

        sensor = InternetHealthSensor(coordinator, mock_entry, DNS_SENSOR)

        assert sensor.native_value is None

    def test_sensor_extra_state_attributes(self, mock_coordinator, mock_entry):
        """Test sensor extra state attributes."""
        sensor = InternetHealthSensor(mock_coordinator, mock_entry, DNS_SENSOR)

        attrs = sensor.extra_state_attributes
        assert attrs["dns_server"] == "1.1.1.1"
        assert attrs["success"] is True

    def test_sensor_extra_state_attributes_no_data(self, mock_entry):
        """Test sensor extra state attributes when no data."""
        coordinator = Mock()
        coordinator.data = None

        sensor = InternetHealthSensor(coordinator, mock_entry, DNS_SENSOR)

        assert sensor.extra_state_attributes == {}

    def test_has_entity_name(self, mock_coordinator, mock_entry):
        """Test that sensor has entity name attribute."""
        sensor = InternetHealthSensor(mock_coordinator, mock_entry, DNS_SENSOR)

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
    async def test_setup_all_sensors(self, mock_hass, mock_entry, mock_coordinator):
        """Test setup creates all sensors when both monitoring types enabled."""
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

        # Should have: 3 hops x 3 sensors (latency, jitter, packet_loss) + 1 dns = 10
        assert len(added_entities) == 10

    @pytest.mark.asyncio
    async def test_setup_gateway_only(self, mock_hass, mock_entry, mock_coordinator):
        """Test setup creates only hop sensors when DNS disabled."""
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

        # Should have: 3 hops x 3 sensors = 9
        assert len(added_entities) == 9

    @pytest.mark.asyncio
    async def test_setup_dns_only(self, mock_hass, mock_entry, mock_coordinator):
        """Test setup creates only DNS sensor when gateway disabled."""
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

        # Should have only 1 DNS sensor
        assert len(added_entities) == 1
        assert added_entities[0].entity_description.key == "dns_latency"

    @pytest.mark.asyncio
    async def test_setup_no_sensors(self, mock_hass, mock_entry, mock_coordinator):
        """Test setup creates no sensors when both disabled."""
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

        # Should have no sensors
        assert len(added_entities) == 0

    @pytest.mark.asyncio
    async def test_sensor_types_created(self, mock_hass, mock_entry, mock_coordinator):
        """Test that correct sensor types are created for each hop."""
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

        # Check we have the right types
        latency_sensors = [e for e in added_entities if isinstance(e, HopLatencySensor)]
        jitter_sensors = [e for e in added_entities if isinstance(e, HopJitterSensor)]
        packet_loss_sensors = [e for e in added_entities if isinstance(e, HopPacketLossSensor)]

        assert len(latency_sensors) == 3
        assert len(jitter_sensors) == 3
        assert len(packet_loss_sensors) == 3
