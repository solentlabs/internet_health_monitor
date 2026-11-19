"""Sensor platform: per-hop latency, jitter and packet loss, and DNS latency."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from solentlabs.internet_health_monitor_core.network_diagnostics import NUM_HOPS, HopInfo, NetworkDiagnosticsResult

from .coordinator import InternetHealthConfigEntry, InternetHealthCoordinator
from .entity import InternetHealthEntity

# Entities only read coordinator data; no per-entity update calls.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HopSensorEntityDescription(SensorEntityDescription):
    """A per-hop measurement; key and translation key carry the hop number."""

    value_fn: Callable[[HopInfo], float | None]


@dataclass(frozen=True, kw_only=True)
class ResultSensorEntityDescription(SensorEntityDescription):
    """A measurement read from the whole poll result."""

    value_fn: Callable[[NetworkDiagnosticsResult], float | None]
    attrs_fn: Callable[[NetworkDiagnosticsResult], dict[str, Any]]


def _hop_descriptions(hop: int) -> tuple[HopSensorEntityDescription, ...]:
    """Latency, jitter and packet loss sensors for one hop."""
    return (
        HopSensorEntityDescription(
            key=f"hop_{hop}_latency",
            translation_key=f"hop_{hop}_latency",
            native_unit_of_measurement=UnitOfTime.MILLISECONDS,
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            value_fn=lambda h: h.latency_ms,
        ),
        HopSensorEntityDescription(
            key=f"hop_{hop}_jitter",
            translation_key=f"hop_{hop}_jitter",
            native_unit_of_measurement=UnitOfTime.MILLISECONDS,
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
            value_fn=lambda h: h.jitter_ms,
        ),
        HopSensorEntityDescription(
            key=f"hop_{hop}_packet_loss",
            translation_key=f"hop_{hop}_packet_loss",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            value_fn=lambda h: h.packet_loss_percent,
        ),
    )


HOP_SENSORS: tuple[HopSensorEntityDescription, ...] = tuple(
    d for hop in range(1, NUM_HOPS + 1) for d in _hop_descriptions(hop)
)

DNS_SENSOR = ResultSensorEntityDescription(
    key="dns_latency",
    translation_key="dns_latency",
    native_unit_of_measurement=UnitOfTime.MILLISECONDS,
    device_class=SensorDeviceClass.DURATION,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
    value_fn=lambda r: r.dns_latency_ms,
    attrs_fn=lambda r: {"dns_server": r.dns_server, "success": r.dns_success},
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InternetHealthConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the sensors for the monitoring types that are switched on."""
    data = entry.runtime_data
    entities: list[SensorEntity] = []
    if data.enable_gateway:
        entities.extend(HopSensor(data.coordinator, d) for d in HOP_SENSORS)
    if data.enable_dns:
        entities.append(ResultSensor(data.coordinator, DNS_SENSOR))
    async_add_entities(entities)


class ResultSensor(InternetHealthEntity, SensorEntity):
    """A sensor read from the whole poll result."""

    entity_description: ResultSensorEntityDescription

    def __init__(self, coordinator: InternetHealthCoordinator, description: ResultSensorEntityDescription) -> None:
        """Attach the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the measurement."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return context for the measurement."""
        return self.entity_description.attrs_fn(self.coordinator.data)


class HopSensor(InternetHealthEntity, SensorEntity):
    """One measurement for one hop; attributes describe the hop."""

    entity_description: HopSensorEntityDescription

    def __init__(self, coordinator: InternetHealthCoordinator, description: HopSensorEntityDescription) -> None:
        """Attach the description and remember the hop number."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._hop_number = int(description.key.split("_")[1])

    def _hop(self) -> HopInfo | None:
        """This sensor's hop in the latest result."""
        return self.coordinator.data.get_hop(self._hop_number)

    @property
    def native_value(self) -> float | None:
        """Return the measurement, or None if the hop was not found."""
        hop = self._hop()
        return self.entity_description.value_fn(hop) if hop else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Describe the hop: address, reachability, name, owner, packet counts."""
        hop = self._hop()
        if not hop:
            return {"hop_number": self._hop_number, "hop_ip": None, "reachable": False}
        attrs: dict[str, Any] = {
            "hop_number": hop.hop_number,
            "hop_ip": hop.ip,
            "reachable": hop.reachable,
            "typical_location": hop.typical_location,
            "packets_sent": hop.packets_sent,
            "packets_received": hop.packets_received,
        }
        if hop.hostname:
            attrs["hostname"] = hop.hostname
        if hop.asn is not None:
            attrs["asn"] = hop.asn
            attrs["as_name"] = hop.as_name
        return attrs
