"""Fixtures: a real in-memory Home Assistant with IHM set up on a scripted poll.

The core's poll and tool check are patched for every test here, so no test
touches the network. `poll` is the AsyncMock behind run_diagnostics: set its
return_value or side_effect to script a result or a failure.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.internet_health_monitor.const import DOMAIN, NAME
from solentlabs.internet_health_monitor_core.network_diagnostics import (
    HopInfo,
    NetworkDiagnostics,
    NetworkDiagnosticsResult,
)
from solentlabs.internet_health_monitor_core.platforms.linux import LinuxPlatform

SetupEntry = Callable[..., Awaitable[MockConfigEntry]]


def make_result(**overrides: Any) -> NetworkDiagnosticsResult:
    """A poll where every target answered; override any field."""
    values: dict[str, Any] = {
        "timestamp": 1.0,
        "gateway_ip": "192.168.1.1",
        "gateway_reachable": True,
        "gateway_latency_ms": 1.2,
        "gateway_jitter_ms": 0.3,
        "packet_loss_percent": 0.0,
        "packets_sent": 3,
        "packets_received": 3,
        "hops": [
            HopInfo(1, "192.168.1.1", 1.2, True, 0.3, 0.0, 3, 3),
            HopInfo(2, "10.0.0.1", 8.5, True, 1.1, 0.0, 3, 3, hostname="isp-router.example.com"),
            HopInfo(3, "198.51.100.1", 12.4, True, 2.0, 33.3, 3, 2, asn=64500, as_name="EXAMPLE-NET"),
        ],
        "dns_server": "192.168.1.1",
        "dns_success": True,
        "dns_latency_ms": 23.5,
        "trace_target": "8.8.8.8",
    }
    values.update(overrides)
    return NetworkDiagnosticsResult(**values)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> Iterator[None]:
    """Let HA load the integration from custom_components/."""
    yield


@pytest.fixture(autouse=True)
def poll() -> Iterator[AsyncMock]:
    """Script the core's poll; no tools are reported missing."""
    mock = AsyncMock(return_value=make_result())
    with (
        patch.object(NetworkDiagnostics, "run_diagnostics", mock),
        patch.object(LinuxPlatform, "missing_tools", return_value=[]),
        patch.object(LinuxPlatform, "missing_optional_tools", return_value=[]),
    ):
        yield mock


@pytest.fixture
async def setup_entry(hass: HomeAssistant) -> AsyncIterator[SetupEntry]:
    """Add an entry with the given options and set it up."""

    async def _setup(**options: Any) -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=DOMAIN,
            title=NAME,
            options=options,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    yield _setup


def entity_id(hass: HomeAssistant, platform: str, entry: MockConfigEntry, key: str) -> str | None:
    """Entity id registered for an entity key, or None if not created."""
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")


async def set_options(hass: HomeAssistant, entry: MockConfigEntry, options: dict[str, Any]) -> None:
    """Save options and reload, as the options flow does (OptionsFlowWithReload)."""
    hass.config_entries.async_update_entry(entry, options=options)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
