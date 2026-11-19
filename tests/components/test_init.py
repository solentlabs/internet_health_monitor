"""Tests for setup, setup checks, option wiring, reload and unload."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.internet_health_monitor.const import (
    CONF_DNS_SERVER,
    CONF_HOP_OWNERSHIP,
    CONF_PING_COUNT,
    DOMAIN,
)
from solentlabs.internet_health_monitor_core.platforms import UnsupportedPlatformError
from solentlabs.internet_health_monitor_core.platforms.linux import LinuxPlatform

from .conftest import SetupEntry

# options -> what reaches the core's config
# fmt: off
OPTION_CASES = [
    ("defaults",   {},                                                       ("auto", 3, False)),
    ("all set",    {CONF_DNS_SERVER: "9.9.9.9", CONF_PING_COUNT: 5, CONF_HOP_OWNERSHIP: True},
                                                                             ("9.9.9.9", 5, True)),
]
# fmt: on


async def test_setup_and_unload(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """A working host loads; unloading releases the entry."""
    entry = await setup_entry()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinator.data.gateway_reachable is True

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(("description", "options", "expected"), OPTION_CASES, ids=[c[0] for c in OPTION_CASES])
async def test_options_reach_core(
    setup_entry: SetupEntry, description: str, options: dict[str, Any], expected: tuple[str, int, bool]
) -> None:
    """Each option is passed to the core's config."""
    entry = await setup_entry(**options)
    config = entry.runtime_data.diagnostics.config
    assert (config.dns_server, config.ping_count, config.hop_ownership) == expected


async def test_missing_tools_is_a_setup_error(setup_entry: SetupEntry) -> None:
    """Without ping or ip nothing can be measured: a permanent, explained error."""
    with patch.object(LinuxPlatform, "missing_tools", return_value=["ping"]):
        entry = await setup_entry()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason is not None and "ping" in entry.reason


async def test_unsupported_platform_is_a_setup_error(setup_entry: SetupEntry) -> None:
    """An OS without probes fails setup instead of reporting nothing."""
    with patch(
        "custom_components.internet_health_monitor.NetworkDiagnostics",
        side_effect=UnsupportedPlatformError("darwin"),
    ):
        entry = await setup_entry()
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_failed_first_poll_retries(setup_entry: SetupEntry, poll: AsyncMock) -> None:
    """A first poll that raises is temporary: HA retries setup."""
    poll.side_effect = OSError("boom")
    entry = await setup_entry()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_options_change_reloads(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Saving options rebuilds the core with the new settings."""
    entry = await setup_entry()
    hass.config_entries.async_update_entry(entry, options={CONF_PING_COUNT: 7})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.diagnostics.config.ping_count == 7


async def test_missing_traceroute_raises_repair_issue(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Without traceroute IHM still runs, and a repair issue tells the user how to fix it."""
    with patch.object(LinuxPlatform, "missing_optional_tools", return_value=["traceroute"]):
        entry = await setup_entry()
    assert entry.state is ConfigEntryState.LOADED
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "traceroute_missing")
    assert issue is not None
    assert issue.translation_key == "traceroute_missing"


async def test_repair_issue_clears_when_installed(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Once traceroute is installed, the next setup removes the issue."""
    with patch.object(LinuxPlatform, "missing_optional_tools", return_value=["traceroute"]):
        entry = await setup_entry()
    with patch.object(LinuxPlatform, "missing_optional_tools", return_value=[]):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "traceroute_missing") is None


async def test_removing_entry_clears_repair_issue(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Deleting the integration leaves no issue behind."""
    with patch.object(LinuxPlatform, "missing_optional_tools", return_value=["traceroute"]):
        entry = await setup_entry()
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "traceroute_missing") is None
