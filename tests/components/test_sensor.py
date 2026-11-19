"""Tests for the sensors, read from HA's state machine."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from custom_components.internet_health_monitor.const import CONF_ENABLE_DNS_MONITORING, CONF_ENABLE_GATEWAY_MONITORING

from .conftest import SetupEntry, entity_id, make_result

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

# monitoring switched off -> sensors that must not exist
SWITCH_CASES = [
    ("gateway off", {CONF_ENABLE_GATEWAY_MONITORING: False}, ["hop_1_latency", "hop_3_packet_loss"],
     ["dns_latency"]),
    ("dns off",     {CONF_ENABLE_DNS_MONITORING: False},     ["dns_latency"], ["hop_1_latency"]),
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
    assert state.attributes["friendly_name"] == "Internet Health Monitor Hop 2 latency (ISP)"


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


async def test_undetected_hop_is_unknown(hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock) -> None:
    """A hop traceroute did not find reads unknown, not zero."""
    poll.return_value = make_result(hops=make_result().hops[:1])
    entry = await setup_entry()
    state = hass.states.get(entity_id(hass, "sensor", entry, "hop_3_latency") or "")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["hop_ip"] is None
