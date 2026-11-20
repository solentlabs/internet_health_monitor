"""Sensor platform: per-hop latency, jitter and packet loss, DNS latency, and the host environment."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfDataRate, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from solentlabs.internet_health_monitor_core.network_diagnostics import NUM_HOPS, HopInfo, NetworkDiagnosticsResult
from solentlabs.internet_health_monitor_core.speed_test import SpeedTestResult

from .coordinator import InternetHealthConfigEntry, InternetHealthCoordinator, SpeedTestCoordinator
from .entity import InternetHealthEntity
from .usage import UsageTotals

# Entities only read coordinator data; no per-entity update calls.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HopSensorEntityDescription(SensorEntityDescription):
    """A per-hop measurement; key and translation key carry the hop number."""

    value_fn: Callable[[HopInfo], float | None]


@dataclass(frozen=True, kw_only=True)
class ResultSensorEntityDescription(SensorEntityDescription):
    """A measurement read from the whole poll result."""

    value_fn: Callable[[NetworkDiagnosticsResult], StateType]
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

# Connection types Core can classify; "unknown" reads as the unknown state.
CONNECTION_TYPES = ["ethernet", "wifi", "bridge", "veth"]

CONNECTION_TYPE_SENSOR = ResultSensorEntityDescription(
    key="connection_type",
    translation_key="connection_type",
    device_class=SensorDeviceClass.ENUM,
    options=CONNECTION_TYPES,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda r: (
        r.host_environment.connection_type
        if r.host_environment and r.host_environment.connection_type in CONNECTION_TYPES
        else None
    ),
    attrs_fn=lambda r: {"interface": r.host_environment.interface_name if r.host_environment else None},
)

# HA's installation_type (helpers/system_info.py) -> state; anything else is unknown.
INSTALL_TYPES: dict[str, str] = {
    "Home Assistant OS": "os",
    "Home Assistant Supervised": "supervised",
    "Home Assistant Container": "container",
    "Home Assistant Core": "core",
    "Unsupported Third Party Container": "third_party_container",
}


@dataclass(frozen=True, kw_only=True)
class SpeedTestSensorEntityDescription(SensorEntityDescription):
    """One field of the latest speed test."""

    value_fn: Callable[[SpeedTestResult], float | None]


def _speed(
    key: str, value_fn: Callable[[SpeedTestResult], float | None], **kwargs: Any
) -> SpeedTestSensorEntityDescription:
    """A speed test sensor; its state_class applies only with Long-term statistics on."""
    return SpeedTestSensorEntityDescription(
        key=f"speed_test_{key}",
        translation_key=f"speed_test_{key}",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=value_fn,
        **kwargs,
    )


_RATE: dict[str, Any] = {
    "native_unit_of_measurement": UnitOfDataRate.MEGABITS_PER_SECOND,
    "device_class": SensorDeviceClass.DATA_RATE,
}
_MS: dict[str, Any] = {
    "native_unit_of_measurement": UnitOfTime.MILLISECONDS,
    "device_class": SensorDeviceClass.DURATION,
}

SPEED_TEST_SENSORS: tuple[SpeedTestSensorEntityDescription, ...] = (
    _speed("download", lambda r: r.download_mbps, **_RATE),
    _speed("upload", lambda r: r.upload_mbps, **_RATE),
    _speed("idle_latency", lambda r: r.idle_latency_ms, **_MS),
    _speed("download_latency", lambda r: r.download_latency_ms, **_MS),
    _speed("upload_latency", lambda r: r.upload_latency_ms, **_MS),
    _speed(
        "data_used",
        lambda r: r.data_used_mb,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
    ),
)


@dataclass(frozen=True, kw_only=True)
class UsageSensorEntityDescription(SensorEntityDescription):
    """One running total of what IHM has sent since install."""

    value_fn: Callable[[UsageTotals], float]


def _usage(key: str, value_fn: Callable[[UsageTotals], float], **kwargs: Any) -> UsageSensorEntityDescription:
    """A diagnostic running total; created only with Usage totals on.

    No state_class: the total is what matters, so no long-term statistics,
    which HA never purges (ADR-013).
    """
    return UsageSensorEntityDescription(
        key=f"usage_{key}",
        translation_key=f"usage_{key}",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=value_fn,
        **kwargs,
    )


_MB: dict[str, Any] = {
    "native_unit_of_measurement": UnitOfInformation.MEGABYTES,
    "device_class": SensorDeviceClass.DATA_SIZE,
    "suggested_display_precision": 1,
}

USAGE_SENSORS: tuple[UsageSensorEntityDescription, ...] = (
    _usage("pings", lambda u: u.pings),
    _usage("traceroutes", lambda u: u.traceroutes),
    _usage("dns_queries", lambda u: u.dns_queries),
    _usage("speed_tests", lambda u: u.speed_tests),
    _usage("downloaded", lambda u: u.downloaded_mb, **_MB),
    _usage("uploaded", lambda u: u.uploaded_mb, **_MB),
)

INSTALL_TYPE_SENSOR = SensorEntityDescription(
    key="install_type",
    translation_key="install_type",
    device_class=SensorDeviceClass.ENUM,
    options=list(INSTALL_TYPES.values()),
    entity_category=EntityCategory.DIAGNOSTIC,
)


def _statistics[D: SensorEntityDescription](description: D, keep: bool) -> D:
    """The description with its state_class, or without it unless the user chose long-term statistics (ADR-013)."""
    return description if keep else replace(description, state_class=None)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InternetHealthConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the sensors for the monitoring types that are switched on."""
    data = entry.runtime_data
    entities: list[SensorEntity] = [
        ResultSensor(data.coordinator, CONNECTION_TYPE_SENSOR),
        InstallTypeSensor(data.coordinator, INSTALL_TYPE_SENSOR),
    ]
    if data.usage_totals:
        entities.extend(UsageSensor(data.coordinator, d) for d in USAGE_SENSORS)
    keep = data.long_term_statistics
    if data.speed_test:
        entities.extend(SpeedTestSensor(data.speed_test, _statistics(d, keep)) for d in SPEED_TEST_SENSORS)
    if data.enable_gateway:
        entities.extend(HopSensor(data.coordinator, _statistics(d, keep)) for d in HOP_SENSORS)
    if data.enable_dns:
        entities.append(ResultSensor(data.coordinator, _statistics(DNS_SENSOR, keep)))
    async_add_entities(entities)


class ResultSensor(InternetHealthEntity[InternetHealthCoordinator], SensorEntity):
    """A sensor read from the whole poll result."""

    entity_description: ResultSensorEntityDescription

    def __init__(self, coordinator: InternetHealthCoordinator, description: ResultSensorEntityDescription) -> None:
        """Attach the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Return the measurement."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return context for the measurement."""
        return self.entity_description.attrs_fn(self.coordinator.data)


class SpeedTestSensor(InternetHealthEntity[SpeedTestCoordinator], SensorEntity):
    """One field of the latest speed test; unknown until a test has run."""

    entity_description: SpeedTestSensorEntityDescription

    def __init__(self, coordinator: SpeedTestCoordinator, description: SpeedTestSensorEntityDescription) -> None:
        """Attach the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | None:
        """Return the field, or None before the first test."""
        result = self.coordinator.data
        return self.entity_description.value_fn(result) if result else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which backend and server measured it, and when."""
        result = self.coordinator.data
        if not result:
            return {}
        tested_at = dt_util.utc_from_timestamp(result.started_at).isoformat()
        return {"backend": result.backend, "server": result.server, "tested_at": tested_at}


class UsageSensor(InternetHealthEntity[InternetHealthCoordinator], SensorEntity):
    """A running total; stays available when a poll fails, since the total is still known."""

    entity_description: UsageSensorEntityDescription

    def __init__(self, coordinator: InternetHealthCoordinator, description: UsageSensorEntityDescription) -> None:
        """Attach the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Totals are known even when the latest poll failed."""
        return True

    @property
    @override
    def native_value(self) -> float:
        """Return the total."""
        return self.entity_description.value_fn(self.coordinator.usage.totals)


class InstallTypeSensor(InternetHealthEntity[InternetHealthCoordinator], SensorEntity):
    """How Home Assistant is installed, as HA itself reports it."""

    def __init__(self, coordinator: InternetHealthCoordinator, description: SensorEntityDescription) -> None:
        """Attach the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> str | None:
        """Return the installation type, or None if HA does not know it."""
        return INSTALL_TYPES.get(self.coordinator.config_entry.runtime_data.installation_type)


class HopSensor(InternetHealthEntity[InternetHealthCoordinator], SensorEntity):
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
    @override
    def native_value(self) -> float | None:
        """Return the measurement, or None if the hop was not found."""
        hop = self._hop()
        return self.entity_description.value_fn(hop) if hop else None

    @property
    @override
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
