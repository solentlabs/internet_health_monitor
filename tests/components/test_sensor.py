"""Tests for the sensors, read from HA's state machine."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.internet_health_monitor.const import CONF_INTERNET_REFERENCE
from solentlabs.internet_health_monitor_core.platforms.base import HostEnvironment

from .conftest import SetupEntry, entity_id, make_result

SYSTEM_INFO = "custom_components.internet_health_monitor.async_get_system_info"

# Long-term statistics option -> state_class on the measurement sensors (ADR-013).
STATISTICS_CASES: list[tuple[bool, str | None]] = [
    (False, None),  # default: HA keeps 10 days of history, nothing that is never purged
    (True, "measurement"),
]
MEASUREMENT_KEYS = ["hop_1_latency", "hop_2_jitter", "hop_3_packet_loss", "dns_latency", "speed_test_download"]


# entity key -> state for the default scripted poll (conftest.make_result)
# fmt: off
STATE_CASES = [
    ("hop_1_latency",     "1.2"),
    ("hop_2_latency",     "8.5"),
    ("hop_3_latency",     "12.4"),
    ("hop_2_jitter",      "1.1"),
    ("hop_3_packet_loss", "33.3"),
    ("dns_latency",       "23.5"),
]

# option -> sensors that must not exist, and ones that still must. Only the internet
# reference can be turned off; gateway, hops and DNS always run (ADR-015, ADR-016).
SWITCH_CASES = [
    ("reference off", {CONF_INTERNET_REFERENCE: "off"}, ["internet_latency", "internet_packet_loss"],
     ["hop_1_latency", "hop_3_packet_loss", "dns_latency"]),
]
# fmt: on


@pytest.mark.parametrize(("key", "expected"), STATE_CASES)
async def test_states(hass: HomeAssistant, setup_entry: SetupEntry, key: str, expected: str) -> None:
    """Each sensor shows its own measurement."""
    entry = await setup_entry()
    state = hass.states.get(entity_id(hass, "sensor", entry, key) or "")
    assert state is not None
    assert state.state == expected


async def test_names_come_from_translations(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Entity names are translated, not hard-coded."""
    entry = await setup_entry()
    state = hass.states.get(entity_id(hass, "sensor", entry, "hop_2_latency") or "")
    assert state is not None
    assert state.attributes["friendly_name"] == "Internet Health Hop 2 latency (ISP)"


@pytest.mark.parametrize(
    ("description", "options", "absent", "present"), SWITCH_CASES, ids=[c[0] for c in SWITCH_CASES]
)
async def test_switches(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    description: str,
    options: dict[str, Any],
    absent: list[str],
    present: list[str],
) -> None:
    """Turning a monitoring type off removes its sensors."""
    entry = await setup_entry(**options)
    assert all(entity_id(hass, "sensor", entry, key) is None for key in absent)
    assert all(entity_id(hass, "sensor", entry, key) is not None for key in present)


async def test_hop_attributes(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Hop sensors describe their hop: address, name and, when looked up, owner."""
    entry = await setup_entry()
    hop2 = hass.states.get(entity_id(hass, "sensor", entry, "hop_2_latency") or "")
    hop3 = hass.states.get(entity_id(hass, "sensor", entry, "hop_3_latency") or "")
    assert hop2 is not None and hop3 is not None
    assert hop2.attributes["hop_ip"] == "10.0.0.1"
    assert hop2.attributes["address_type"] == "private"
    assert "typical_location" not in hop2.attributes
    assert hop2.attributes["hostname"] == "isp-router.example.com"
    assert "asn" not in hop2.attributes
    assert (hop3.attributes["asn"], hop3.attributes["as_name"]) == (64500, "EXAMPLE-NET")
    assert hop3.attributes["packets_received"] == 2


async def test_dns_attributes(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """The DNS sensor names the server it timed."""
    entry = await setup_entry()
    state = hass.states.get(entity_id(hass, "sensor", entry, "dns_latency") or "")
    assert state is not None
    assert state.attributes["dns_server"] == "192.168.1.1"
    assert state.attributes["dns_source"] == "system"


async def test_undetected_hop_is_unknown(hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock) -> None:
    """A hop traceroute did not find reads unknown, not zero."""
    poll.return_value = make_result(hops=make_result().hops[:1])
    entry = await setup_entry()
    state = hass.states.get(entity_id(hass, "sensor", entry, "hop_3_latency") or "")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["hop_ip"] is None


# ┌──────────────────────────────────────────┬──────────────┬────────────┬──────────────────────────────┐
# │ host environment in the poll             │ state        │ interface  │ description                  │
# ├──────────────────────────────────────────┼──────────────┼────────────┼──────────────────────────────┤
# │ wifi on wlan0                            │ wifi         │ wlan0      │ classified                   │
# │ ethernet on eth0                         │ ethernet     │ eth0       │ classified                   │
# │ unknown on wg0                           │ unknown      │ wg0        │ unclassified name            │
# │ not detected yet                         │ unknown      │ None       │ before detection             │
# └──────────────────────────────────────────┴──────────────┴────────────┴──────────────────────────────┘
# fmt: off
CONNECTION_CASES: list[tuple[HostEnvironment | None, str, str | None, str]] = [
    (HostEnvironment("wifi", "wlan0"),     "wifi",        "wlan0", "wifi"),
    (HostEnvironment("ethernet", "eth0"),  "ethernet",    "eth0",  "ethernet"),
    (HostEnvironment("unknown", "wg0"),    STATE_UNKNOWN, "wg0",   "unclassified"),
    (None,                                 STATE_UNKNOWN, None,    "not_detected"),
]
# fmt: on


@pytest.mark.parametrize("env,expected,interface,desc", CONNECTION_CASES, ids=[c[3] for c in CONNECTION_CASES])
async def test_connection_type(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    poll: AsyncMock,
    env: HostEnvironment | None,
    expected: str,
    interface: str | None,
    desc: str,
) -> None:
    """Connection type reads the default route's interface; unclassified is unknown."""
    poll.return_value = make_result(host_environment=env)
    entry = await setup_entry()
    state = hass.states.get(entity_id(hass, "sensor", entry, "connection_type") or "")
    assert state is not None
    assert (state.state, state.attributes.get("interface")) == (expected, interface), desc


# ┌───────────────────────────────────────┬────────────────────────┐
# │ HA's installation_type                │ state                  │
# ├───────────────────────────────────────┼────────────────────────┤
# │ Home Assistant OS                     │ os                     │
# │ Home Assistant Supervised             │ supervised             │
# │ Home Assistant Container              │ container              │
# │ Home Assistant Core                   │ core                   │
# │ Unsupported Third Party Container     │ third_party_container  │
# │ Unknown                               │ unknown                │
# └───────────────────────────────────────┴────────────────────────┘
# fmt: off
INSTALL_CASES: list[tuple[str, str]] = [
    ("Home Assistant OS",                 "os"),
    ("Home Assistant Supervised",         "supervised"),
    ("Home Assistant Container",          "container"),
    ("Home Assistant Core",               "core"),
    ("Unsupported Third Party Container", "third_party_container"),
    ("Unknown",                           STATE_UNKNOWN),
]
# fmt: on


@pytest.mark.parametrize("reported,expected", INSTALL_CASES)
async def test_install_type(hass: HomeAssistant, setup_entry: SetupEntry, reported: str, expected: str) -> None:
    """Install type is HA's own installation_type, as an enum state."""
    with patch(SYSTEM_INFO, AsyncMock(return_value={"installation_type": reported})):
        entry = await setup_entry()
    state = hass.states.get(entity_id(hass, "sensor", entry, "install_type") or "")
    assert state is not None
    assert state.state == expected


async def test_environment_sensors_are_diagnostic_and_always_created(
    hass: HomeAssistant, setup_entry: SetupEntry
) -> None:
    """Both environment sensors are diagnostic enums, created on every install."""
    entry = await setup_entry(**{CONF_INTERNET_REFERENCE: "off"})
    registry = er.async_get(hass)
    for key in ("connection_type", "install_type"):
        entity = registry.async_get(entity_id(hass, "sensor", entry, key) or "")
        assert entity is not None
        assert entity.entity_category is EntityCategory.DIAGNOSTIC
        assert entity.original_device_class is SensorDeviceClass.ENUM


@pytest.mark.parametrize(("on", "expected"), STATISTICS_CASES, ids=["off", "on"])
async def test_long_term_statistics_option(
    hass: HomeAssistant, setup_entry: SetupEntry, on: bool, expected: str | None
) -> None:
    """Measurement sensors carry a state_class, and so long-term statistics, only when the user chooses."""
    entry = await setup_entry(speed_test_backend="cloudflare", long_term_statistics=on)
    for key in MEASUREMENT_KEYS:
        registered = er.async_get(hass).async_get(entity_id(hass, "sensor", entry, key) or "")
        assert registered is not None, key
        assert (registered.capabilities or {}).get("state_class") == expected, key


async def test_internet_reference_sensors(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """The internet reference reads like a hop: latency, jitter and loss, naming its address (ADR-015)."""
    entry = await setup_entry()
    readings = {}
    for key in ("internet_latency", "internet_jitter", "internet_packet_loss"):
        state = hass.states.get(entity_id(hass, "sensor", entry, key) or "")
        assert state is not None, key
        readings[key] = float(state.state)
        assert (state.attributes["reference_ip"], state.attributes["reachable"]) == ("1.1.1.1", True)
        assert (state.attributes["packets_sent"], state.attributes["packets_received"]) == (3, 3)
    assert readings == {"internet_latency": 15.2, "internet_jitter": 0.4, "internet_packet_loss": 0.0}
