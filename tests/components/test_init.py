"""Tests for setup, setup checks, option wiring, reload and unload."""

from __future__ import annotations

import logging
from ipaddress import IPv4Address
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from aiohasupervisor import SupervisorError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.internet_health_monitor.const import (
    CONF_DNS_SERVER,
    CONF_HOP_OWNERSHIP,
    CONF_INTERNET_REFERENCE,
    CONF_PING_COUNT,
    DOMAIN,
    VERSION,
)
from solentlabs.internet_health_monitor_core.platforms import UnsupportedPlatformError
from solentlabs.internet_health_monitor_core.platforms.linux import LinuxPlatform

from .conftest import SetupEntry, entity_id, set_options

# options -> what reaches the core's config
# fmt: off
OPTION_CASES = [
    ("defaults",   {},                                                       ("auto", 3, False)),
    ("all set",    {CONF_DNS_SERVER: "quad9", CONF_PING_COUNT: 5, CONF_HOP_OWNERSHIP: True},
                                                                             ("9.9.9.9", 5, True)),
    ("stored address", {CONF_DNS_SERVER: "1.1.1.1"},                         ("1.1.1.1", 3, False)),
]
# fmt: on


def _interface(primary: bool, *nameservers: str, ipv4: bool = True) -> SimpleNamespace:
    """A Supervisor network interface with the given IPv4 nameservers."""
    v4 = SimpleNamespace(nameservers=[IPv4Address(n) for n in nameservers]) if ipv4 else None
    return SimpleNamespace(primary=primary, ipv4=v4)


# Auto DNS under the Supervisor -> (server, source) passed to Core: the host's own
# resolver from the Supervisor's network info, not its DNS forwarder (ARCHITECTURE.md
# § One Poll). Otherwise auto is left to Core, which reports the source itself (None).
ROUTER = [_interface(True, "192.168.1.1", "192.168.1.2")]
SECOND = [_interface(False, "10.0.0.1"), _interface(True, "192.168.1.1")]
NO_IPV4 = [_interface(True, ipv4=False)]
HOST = ("192.168.1.1", "host")
CORE = ("auto", None)
# fmt: off
SUPERVISOR_DNS_CASES: list[tuple[str, bool, dict[str, Any], Any, tuple[str, str | None]]] = [
    # (description,               supervisor, options,                    network info,            expected)
    ("not a Supervisor install",  False, {},                              ROUTER,                  CORE),
    ("primary's first server",    True,  {},                              ROUTER,                  HOST),
    ("primary listed second",     True,  {},                              SECOND,                  HOST),
    ("primary has no servers",    True,  {},                              [_interface(True)],      CORE),
    ("primary has no IPv4",       True,  {},                              NO_IPV4,                 CORE),
    ("Supervisor error",          True,  {},                              SupervisorError("down"), CORE),
    ("chosen server kept",        True,  {CONF_DNS_SERVER: "quad9"},      ROUTER,                  ("9.9.9.9", None)),
]
# fmt: on


# Internet reference option -> address the core pings (ADR-015)
# fmt: off
REFERENCE_OPTION_CASES: list[tuple[str, dict[str, Any], str | None]] = [
    ("default",          {},                                   "1.1.1.1"),
    ("listed provider",  {CONF_INTERNET_REFERENCE: "google"},  "8.8.8.8"),
    ("typed address",    {CONF_INTERNET_REFERENCE: "8.8.4.4"}, "8.8.4.4"),
    ("off",              {CONF_INTERNET_REFERENCE: "off"},     None),
]
# fmt: on


@pytest.mark.parametrize(
    ("description", "options", "expected"), REFERENCE_OPTION_CASES, ids=[c[0] for c in REFERENCE_OPTION_CASES]
)
async def test_internet_reference_reaches_core(
    setup_entry: SetupEntry, description: str, options: dict[str, Any], expected: str | None
) -> None:
    """The chosen internet reference, or none, is what the core pings."""
    entry = await setup_entry(**options)
    assert entry.runtime_data.diagnostics.config.internet_reference == expected


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


@pytest.mark.parametrize(
    ("description", "supervisor", "options", "network", "expected"),
    SUPERVISOR_DNS_CASES,
    ids=[c[0] for c in SUPERVISOR_DNS_CASES],
)
async def test_auto_dns_under_supervisor(
    setup_entry: SetupEntry,
    description: str,
    supervisor: bool,
    options: dict[str, Any],
    network: Any,
    expected: tuple[str, str | None],
) -> None:
    """Auto times the host's resolver, which the Supervisor reports, not its own forwarder."""
    info = (
        AsyncMock(side_effect=network)
        if isinstance(network, Exception)
        else AsyncMock(return_value=SimpleNamespace(interfaces=network))
    )
    client = SimpleNamespace(network=SimpleNamespace(info=info))
    with (
        patch("custom_components.internet_health_monitor.is_hassio", return_value=supervisor),
        patch("custom_components.internet_health_monitor.get_supervisor_client", return_value=client),
    ):
        entry = await setup_entry(**options)
    config = entry.runtime_data.diagnostics.config
    assert (config.dns_server, config.dns_source) == expected


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
    """Saving the options form reloads the entry, so the core runs with the new settings."""
    entry = await setup_entry()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {CONF_PING_COUNT: 7})
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


async def test_poll_interval_comes_from_core(setup_entry: SetupEntry) -> None:
    """The integration polls at Core's POLL_INTERVAL_S (ADR-007), not a value of its own."""
    from datetime import timedelta

    from solentlabs.internet_health_monitor_core.timing import POLL_INTERVAL_S

    entry = await setup_entry()
    assert entry.runtime_data.coordinator.update_interval == timedelta(seconds=POLL_INTERVAL_S)


# ┌──────────────────────────────────┬──────────────────────────────┬──────────────────────────────────┐
# │ options changed to               │ removed                      │ description                      │
# ├──────────────────────────────────┼──────────────────────────────┼──────────────────────────────────┤
# │ internet reference off           │ the three internet sensors   │ reference entities not created   │
# └──────────────────────────────────┴──────────────────────────────┴──────────────────────────────────┘
# fmt: off
STALE_CASES: list[tuple[dict[str, Any], set[tuple[str, str]], str]] = [
    ({CONF_INTERNET_REFERENCE: "off"},
     {("sensor", "internet_latency"), ("sensor", "internet_jitter"), ("sensor", "internet_packet_loss")},
                                                                          "reference_off"),
]
# fmt: on


@pytest.mark.parametrize("changed,removed,desc", STALE_CASES, ids=[c[2] for c in STALE_CASES])
async def test_entities_no_longer_created_are_removed(
    hass: HomeAssistant, setup_entry: SetupEntry, changed: dict[str, Any], removed: set[tuple[str, str]], desc: str
) -> None:
    """Turning monitoring off removes its entities; turning it back on restores the same ids."""
    entry = await setup_entry()
    before = {key: entity_id(hass, platform, entry, key) for platform, key in removed}
    disabled_button = entity_id(hass, "button", entry, "reset_cache")

    await set_options(hass, entry, {**entry.options, **changed})
    assert all(entity_id(hass, platform, entry, key) is None for platform, key in removed), desc
    assert entity_id(hass, "button", entry, "reset_cache") == disabled_button  # disabled by default, still created

    await set_options(hass, entry, {})
    assert {key: entity_id(hass, platform, entry, key) for platform, key in removed} == before


# Installed Core version -> the startup line, as Cable Modem Monitor's: the integration's version,
# HA's install type, then Core's version as installed, so a mismatch shows in the first line.
# fmt: off
STARTUP_CASES: list[tuple[str, str | None, str]] = [
    ("core installed",   "0.1.0b3", "Internet Health Monitor v{v} starting [Home Assistant OS] — core: v0.1.0b3"),
    ("core not found",   None,      "Internet Health Monitor v{v} starting [Home Assistant OS] — core: not installed"),
]
# fmt: on


@pytest.mark.parametrize(("description", "core", "expected"), STARTUP_CASES, ids=[c[0] for c in STARTUP_CASES])
async def test_startup_line(
    setup_entry: SetupEntry, caplog: pytest.LogCaptureFixture, description: str, core: str | None, expected: str
) -> None:
    """Setup logs one line naming the integration, the install type and the installed Core."""
    from importlib.metadata import PackageNotFoundError

    def installed(package: str) -> str:
        if core is None:
            raise PackageNotFoundError(package)
        return core

    with (
        patch("custom_components.internet_health_monitor.package_version", side_effect=installed),
        patch(
            "custom_components.internet_health_monitor.async_get_system_info",
            AsyncMock(return_value={"installation_type": "Home Assistant OS"}),
        ),
        caplog.at_level(logging.INFO, logger="custom_components.internet_health_monitor"),
    ):
        await setup_entry()
    assert expected.format(v=VERSION) in caplog.messages
