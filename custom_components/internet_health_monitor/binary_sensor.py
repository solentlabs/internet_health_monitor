"""Binary sensor platform for Internet Health Monitor."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnosticsResult

from .const import DOMAIN, MANUFACTURER, NAME

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class InternetHealthBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Internet Health Monitor binary sensor entity."""

    value_fn: Callable[[NetworkDiagnosticsResult], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[InternetHealthBinarySensorEntityDescription, ...] = (
    InternetHealthBinarySensorEntityDescription(
        key="gateway_reachable",
        translation_key="gateway_reachable",
        name="Gateway Reachable",
        icon="mdi:lan-check",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.gateway_reachable,
    ),
    InternetHealthBinarySensorEntityDescription(
        key="internet_reachable",
        translation_key="internet_reachable",
        name="Internet Reachable",
        icon="mdi:web-check",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.dns_success,
    ),
)


GATEWAY_BINARY_SENSORS = {"gateway_reachable"}
DNS_BINARY_SENSORS = {"internet_reachable"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Internet Health Monitor binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    config = data["config"]

    enable_gateway = config.get("enable_gateway", True)
    enable_dns = config.get("enable_dns", True)

    entities = []
    for description in BINARY_SENSOR_DESCRIPTIONS:
        # Filter based on enabled monitoring types
        if description.key in GATEWAY_BINARY_SENSORS and not enable_gateway:
            continue
        if description.key in DNS_BINARY_SENSORS and not enable_dns:
            continue
        entities.append(InternetHealthBinarySensor(coordinator, entry, description))

    async_add_entities(entities)


class InternetHealthBinarySensor(
    CoordinatorEntity[DataUpdateCoordinator[NetworkDiagnosticsResult]], BinarySensorEntity
):
    """Binary sensor for Internet Health Monitor."""

    _attr_has_entity_name = True
    entity_description: InternetHealthBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult],
        entry: ConfigEntry,
        description: InternetHealthBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
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
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.coordinator.data:
            return self.entity_description.value_fn(self.coordinator.data)
        return None
