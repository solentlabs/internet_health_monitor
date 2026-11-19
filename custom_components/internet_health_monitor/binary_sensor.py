"""Binary sensor platform: gateway and internet reachability."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (  # public in HA, not in its __all__
    BinarySensorDeviceClass,  # pyright: ignore[reportPrivateImportUsage]
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import (
    InternetHealthConfigEntry,
    InternetHealthCoordinator,
    InternetHealthRuntimeData,
    ReachabilityTarget,
)
from .entity import InternetHealthEntity

# Entities only read coordinator data; no per-entity update calls.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ReachabilityEntityDescription(BinarySensorEntityDescription):
    """A reachability state read from the poll result."""

    target: ReachabilityTarget
    enabled_fn: Callable[[InternetHealthRuntimeData], bool]


BINARY_SENSORS: tuple[ReachabilityEntityDescription, ...] = (
    ReachabilityEntityDescription(
        key="gateway_reachable",
        translation_key="gateway_reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        target="gateway",
        enabled_fn=lambda d: d.enable_gateway,
    ),
    ReachabilityEntityDescription(
        key="internet_reachable",
        translation_key="internet_reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        target="internet",
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


class ReachabilitySensor(InternetHealthEntity[InternetHealthCoordinator], BinarySensorEntity):
    """On when the target answers; off only once quick checks confirm a failure (ADR-012)."""

    entity_description: ReachabilityEntityDescription

    def __init__(self, coordinator: InternetHealthCoordinator, description: ReachabilityEntityDescription) -> None:
        """Attach the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """Whether the target answers, confirmed by quick checks before turning off (ADR-012)."""
        return self.coordinator.reachability[self.entity_description.target].reachable
