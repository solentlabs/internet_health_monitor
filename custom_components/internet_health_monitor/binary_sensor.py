"""Binary sensor platform: gateway and internet reachability."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnosticsResult

from .coordinator import InternetHealthConfigEntry, InternetHealthCoordinator, InternetHealthRuntimeData
from .entity import InternetHealthEntity

# Entities only read coordinator data; no per-entity update calls.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ReachabilityEntityDescription(BinarySensorEntityDescription):
    """A reachability state read from the poll result."""

    value_fn: Callable[[NetworkDiagnosticsResult], bool | None]
    enabled_fn: Callable[[InternetHealthRuntimeData], bool]


BINARY_SENSORS: tuple[ReachabilityEntityDescription, ...] = (
    ReachabilityEntityDescription(
        key="gateway_reachable",
        translation_key="gateway_reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda r: r.gateway_reachable,
        enabled_fn=lambda d: d.enable_gateway,
    ),
    ReachabilityEntityDescription(
        key="internet_reachable",
        translation_key="internet_reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda r: r.dns_success,
        enabled_fn=lambda d: d.enable_dns,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InternetHealthConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the binary sensors for the monitoring types that are switched on."""
    data = entry.runtime_data
    async_add_entities(ReachabilitySensor(data.coordinator, d) for d in BINARY_SENSORS if d.enabled_fn(data))


class ReachabilitySensor(InternetHealthEntity, BinarySensorEntity):
    """On when the target answered in the latest poll."""

    entity_description: ReachabilityEntityDescription

    def __init__(self, coordinator: InternetHealthCoordinator, description: ReachabilityEntityDescription) -> None:
        """Attach the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @override
    @property
    def is_on(self) -> bool | None:
        """Return whether the target answered."""
        return self.entity_description.value_fn(self.coordinator.data)
