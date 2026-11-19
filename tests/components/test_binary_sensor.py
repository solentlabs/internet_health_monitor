"""Tests for the reachability binary sensors."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.internet_health_monitor.const import CONF_ENABLE_DNS_MONITORING

from .conftest import SetupEntry, entity_id, make_result

# poll result -> (gateway reachable, internet reachable)
# fmt: off
REACHABILITY_CASES = [
    ("both answer",     {},                                                  (STATE_ON, STATE_ON)),
    ("gateway silent",  {"gateway_reachable": False},                        (STATE_OFF, STATE_ON)),
    ("dns failed",      {"dns_success": False, "dns_latency_ms": None},      (STATE_ON, STATE_OFF)),
]
# fmt: on


@pytest.mark.parametrize(
    ("description", "overrides", "expected"), REACHABILITY_CASES, ids=[c[0] for c in REACHABILITY_CASES]
)
async def test_reachability(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    poll: AsyncMock,
    description: str,
    overrides: dict[str, Any],
    expected: tuple[str, str],
) -> None:
    """Each sensor is on when its target answered in the latest poll."""
    poll.return_value = make_result(**overrides)
    entry = await setup_entry()
    states = tuple(
        hass.states.get(entity_id(hass, "binary_sensor", entry, key) or "").state  # type: ignore[union-attr]
        for key in ("gateway_reachable", "internet_reachable")
    )
    assert states == expected


async def test_dns_off_removes_internet_sensor(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """With DNS monitoring off there is no internet reachability sensor."""
    entry = await setup_entry(**{CONF_ENABLE_DNS_MONITORING: False})
    assert entity_id(hass, "binary_sensor", entry, "internet_reachable") is None
    assert entity_id(hass, "binary_sensor", entry, "gateway_reachable") is not None


async def test_failed_poll_makes_entities_unavailable(
    hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock
) -> None:
    """A failed poll is unavailable, not 'off': a broken monitor is not an outage."""
    entry = await setup_entry()
    poll.side_effect = OSError("boom")
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id(hass, "binary_sensor", entry, "gateway_reachable") or "")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
