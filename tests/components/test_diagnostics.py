"""Tests for the diagnostics download."""

from __future__ import annotations

import logging

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from custom_components.internet_health_monitor.const import CONF_PING_COUNT, VERSION
from custom_components.internet_health_monitor.diagnostics import async_get_config_entry_diagnostics
from custom_components.internet_health_monitor.log_buffer import LOGGERS

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
    # The stored usage totals, with or without the Usage totals sensors (off here)
    assert set(data["usage"]) == {"pings", "traceroutes", "dns_queries", "speed_tests", "downloaded_mb", "uploaded_mb"}
    assert data["usage"] == entry.runtime_data.coordinator.usage.totals.to_dict()


async def test_diagnostics_carry_redacted_logs(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """IHM's recent log records come with the download; hostnames and public addresses do not."""
    entry = await setup_entry()
    logging.getLogger(LOGGERS[1]).warning("No hops detected toward 198.51.100.9")
    data = await async_get_config_entry_diagnostics(hass, entry)

    assert any(r["message"] == f"No hops detected toward {REDACTED}" for r in data["logs"])
    assert any("version" in r["message"] and r["level"] == "INFO" for r in data["logs"])  # from setup on
    hops = data["result"]["hops"]
    assert hops[1]["hostname"] == REDACTED
    assert hops[2]["ip"] == REDACTED
    assert (hops[0]["ip"], data["result"]["trace_target"]) == ("192.168.1.1", "8.8.8.8")
    assert hops[2]["asn"] == 64500  # the network a hop belongs to stays
