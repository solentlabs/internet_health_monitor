"""Sensor platform for HA Network Diagnostics."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

if TYPE_CHECKING:
    from .core.network_diagnostics import NetworkDiagnosticsResult

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Network Diagnostics sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        GatewayLatencySensor(coordinator, entry),
        GatewayJitterSensor(coordinator, entry),
        PacketLossSensor(coordinator, entry),
        ISPLatencySensor(coordinator, entry),
        DNSLatencySensor(coordinator, entry),
    ]

    async_add_entities(entities)


class NetworkDiagnosticsSensor(CoordinatorEntity, SensorEntity):
    """Base class for Network Diagnostics sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._key = key

        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Network Diagnostics",
            "manufacturer": "HA Network Diagnostics",
            "model": "Network Monitor",
        }


class GatewayLatencySensor(NetworkDiagnosticsSensor):
    """Sensor for gateway latency."""

    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            entry,
            "gateway_latency",
            "Gateway Latency",
            "mdi:lan-pending",
        )

    @property
    def native_value(self) -> float | None:
        """Return the gateway latency."""
        if self.coordinator.data:
            return self.coordinator.data.gateway_latency_ms
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "gateway_ip": self.coordinator.data.gateway_ip,
            "reachable": self.coordinator.data.gateway_reachable,
        }


class GatewayJitterSensor(NetworkDiagnosticsSensor):
    """Sensor for gateway jitter."""

    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            entry,
            "gateway_jitter",
            "Gateway Jitter",
            "mdi:chart-timeline-variant",
        )

    @property
    def native_value(self) -> float | None:
        """Return the jitter value."""
        if self.coordinator.data:
            return self.coordinator.data.gateway_jitter_ms
        return None


class PacketLossSensor(NetworkDiagnosticsSensor):
    """Sensor for packet loss percentage."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            entry,
            "packet_loss",
            "Packet Loss",
            "mdi:network-off",
        )

    @property
    def native_value(self) -> float | None:
        """Return the packet loss percentage."""
        if self.coordinator.data:
            return self.coordinator.data.packet_loss_percent
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "packets_sent": self.coordinator.data.packets_sent,
            "packets_received": self.coordinator.data.packets_received,
        }


class ISPLatencySensor(NetworkDiagnosticsSensor):
    """Sensor for ISP first hop latency."""

    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            entry,
            "isp_latency",
            "ISP Latency",
            "mdi:wan",
        )

    @property
    def native_value(self) -> float | None:
        """Return the ISP latency."""
        if self.coordinator.data:
            return self.coordinator.data.isp_hop_latency_ms
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "isp_hop_ip": self.coordinator.data.isp_hop_ip,
            "reachable": self.coordinator.data.isp_hop_reachable,
        }


class DNSLatencySensor(NetworkDiagnosticsSensor):
    """Sensor for DNS resolution latency."""

    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            entry,
            "dns_latency",
            "DNS Latency",
            "mdi:dns",
        )

    @property
    def native_value(self) -> float | None:
        """Return the DNS latency."""
        if self.coordinator.data:
            return self.coordinator.data.dns_latency_ms
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "dns_server": self.coordinator.data.dns_server,
            "success": self.coordinator.data.dns_success,
        }
