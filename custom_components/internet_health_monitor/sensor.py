"""Sensor platform for Internet Health Monitor."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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

from .const import DOMAIN, MANUFACTURER, NAME
from .core.network_diagnostics import NUM_HOPS, HopInfo, NetworkDiagnosticsResult

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class InternetHealthSensorEntityDescription(SensorEntityDescription):
    """Describes Internet Health Monitor sensor entity."""

    value_fn: Callable[[NetworkDiagnosticsResult], float | None]
    extra_attrs_fn: Callable[[NetworkDiagnosticsResult], dict[str, Any]] | None = None


# DNS sensor description - the only non-hop sensor
DNS_SENSOR = InternetHealthSensorEntityDescription(
    key="dns_latency",
    translation_key="dns_latency",
    name="DNS Latency",
    icon="mdi:dns",
    native_unit_of_measurement=UnitOfTime.MILLISECONDS,
    device_class=SensorDeviceClass.DURATION,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
    value_fn=lambda data: data.dns_latency_ms,
    extra_attrs_fn=lambda data: {
        "dns_server": data.dns_server,
        "success": data.dns_success,
    },
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Internet Health Monitor sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    config = data["config"]

    enable_gateway = config.get("enable_gateway", True)
    enable_dns = config.get("enable_dns", True)

    entities: list[SensorEntity] = []

    # Add hop sensors if gateway monitoring enabled
    # Each hop gets: latency, jitter, packet loss (3 sensors x 3 hops = 9 sensors)
    if enable_gateway:
        for hop_num in range(1, NUM_HOPS + 1):
            entities.append(HopLatencySensor(coordinator, entry, hop_num))
            entities.append(HopJitterSensor(coordinator, entry, hop_num))
            entities.append(HopPacketLossSensor(coordinator, entry, hop_num))

    # Add DNS sensor if enabled
    if enable_dns:
        entities.append(InternetHealthSensor(coordinator, entry, DNS_SENSOR))

    async_add_entities(entities)


class InternetHealthSensor(CoordinatorEntity[DataUpdateCoordinator[NetworkDiagnosticsResult]], SensorEntity):
    """Sensor for Internet Health Monitor."""

    _attr_has_entity_name = True
    entity_description: InternetHealthSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
        description: InternetHealthSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": MANUFACTURER,
            "model": NAME,
        }

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        if self.coordinator.data:
            return self.entity_description.value_fn(self.coordinator.data)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.data or not self.entity_description.extra_attrs_fn:
            return {}
        return self.entity_description.extra_attrs_fn(self.coordinator.data)


class HopSensorBase(CoordinatorEntity[DataUpdateCoordinator[NetworkDiagnosticsResult]], SensorEntity):
    """Base class for hop sensors."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    # Hop location names
    HOP_NAMES = {1: "Gateway", 2: "ISP", 3: "Backbone"}

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
        hop_number: int,
    ) -> None:
        """Initialize the hop sensor."""
        super().__init__(coordinator)
        self._hop_number = hop_number
        self._entry_id = entry.entry_id

        # Device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": NAME,
            "manufacturer": MANUFACTURER,
            "model": NAME,
        }

    def _get_hop(self) -> HopInfo | None:
        """Get the hop data for this sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get_hop(self._hop_number)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return common hop attributes including rich metadata."""
        hop = self._get_hop()
        if not hop:
            return {"hop_number": self._hop_number, "hop_ip": None, "reachable": False}

        attrs = {
            "hop_number": hop.hop_number,
            "hop_ip": hop.ip,
            "reachable": hop.reachable,
            "typical_location": hop.typical_location,
        }

        # Add metadata if available
        if hop.metadata:
            attrs["hostname"] = hop.metadata.hostname
            attrs["isp"] = hop.metadata.isp
            attrs["org"] = hop.metadata.org
            attrs["asn"] = hop.metadata.asn
            attrs["city"] = hop.metadata.city
            attrs["region"] = hop.metadata.region
            attrs["country"] = hop.metadata.country
            attrs["country_code"] = hop.metadata.country_code
            attrs["mac_vendor"] = hop.metadata.mac_vendor
        elif hop.hostname:
            attrs["hostname"] = hop.hostname

        return attrs


class HopLatencySensor(HopSensorBase):
    """Sensor for individual network hop latency."""

    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
        hop_number: int,
    ) -> None:
        """Initialize the hop latency sensor."""
        super().__init__(coordinator, entry, hop_number)
        hop_name = self.HOP_NAMES.get(hop_number, f"Hop {hop_number}")
        self._attr_unique_id = f"{entry.entry_id}_hop_{hop_number}_latency"
        self._attr_translation_key = f"hop_{hop_number}_latency"
        self._attr_name = f"Hop {hop_number} Latency ({hop_name})"
        self._attr_icon = self._get_icon_for_hop(hop_number)

    @staticmethod
    def _get_icon_for_hop(hop_number: int) -> str:
        """Return appropriate icon based on hop number."""
        if hop_number == 1:
            return "mdi:router-wireless"
        if hop_number == 2:
            return "mdi:wan"
        return "mdi:server-network"

    @property
    def native_value(self) -> float | None:
        """Return the hop latency value."""
        hop = self._get_hop()
        return hop.latency_ms if hop else None


class HopJitterSensor(HopSensorBase):
    """Sensor for individual network hop jitter."""

    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:chart-timeline-variant"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
        hop_number: int,
    ) -> None:
        """Initialize the hop jitter sensor."""
        super().__init__(coordinator, entry, hop_number)
        hop_name = self.HOP_NAMES.get(hop_number, f"Hop {hop_number}")
        self._attr_unique_id = f"{entry.entry_id}_hop_{hop_number}_jitter"
        self._attr_translation_key = f"hop_{hop_number}_jitter"
        self._attr_name = f"Hop {hop_number} Jitter ({hop_name})"

    @property
    def native_value(self) -> float | None:
        """Return the hop jitter value."""
        hop = self._get_hop()
        return hop.jitter_ms if hop else None


class HopPacketLossSensor(HopSensorBase):
    """Sensor for individual network hop packet loss."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:network-off"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
        hop_number: int,
    ) -> None:
        """Initialize the hop packet loss sensor."""
        super().__init__(coordinator, entry, hop_number)
        hop_name = self.HOP_NAMES.get(hop_number, f"Hop {hop_number}")
        self._attr_unique_id = f"{entry.entry_id}_hop_{hop_number}_packet_loss"
        self._attr_translation_key = f"hop_{hop_number}_packet_loss"
        self._attr_name = f"Hop {hop_number} Packet Loss ({hop_name})"

    @property
    def native_value(self) -> float | None:
        """Return the hop packet loss value."""
        hop = self._get_hop()
        return hop.packet_loss_percent if hop else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return packet loss specific attributes."""
        attrs = super().extra_state_attributes
        hop = self._get_hop()
        if hop:
            attrs["packets_sent"] = hop.packets_sent
            attrs["packets_received"] = hop.packets_received
        return attrs
