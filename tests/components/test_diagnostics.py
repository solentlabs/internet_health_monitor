"""Tests for the diagnostics download."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.internet_health_monitor.const import CONF_PING_COUNT, VERSION
from custom_components.internet_health_monitor.diagnostics import async_get_config_entry_diagnostics

from .conftest import SetupEntry


async def test_diagnostics(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """The download has the settings, poll state, latest result and detection state."""
    entry = await setup_entry(**{CONF_PING_COUNT: 4})
    data = await async_get_config_entry_diagnostics(hass, entry)

    assert data["version"] == VERSION
    assert data["options"] == {CONF_PING_COUNT: 4}
    assert data["coordinator"]["last_update_success"] is True
    assert data["result"]["hops"][2]["asn"] == 64500
    assert data["detection_state"]["platform"] == "linux"
