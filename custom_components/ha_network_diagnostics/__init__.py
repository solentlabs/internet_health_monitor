"""HA Network Diagnostics - Home Assistant Integration.

Provides network health monitoring including:
- Gateway latency and reachability
- Jitter (latency variance)
- Packet loss percentage
- DNS resolution timing
- Environment detection (wifi/ethernet, container/native)
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DNS_SERVER,
    CONF_PING_COUNT,
    CONF_SCAN_INTERVAL,
    DEFAULT_DNS_SERVER,
    DEFAULT_PING_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .core.network_diagnostics import NetworkDiagnostics

if TYPE_CHECKING:
    from .core.network_diagnostics import NetworkDiagnosticsResult

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Network Diagnostics from a config entry."""
    _LOGGER.debug("Setting up Network Diagnostics integration")

    # Get configuration
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    dns_server = entry.options.get(CONF_DNS_SERVER, DEFAULT_DNS_SERVER)
    ping_count = entry.options.get(CONF_PING_COUNT, DEFAULT_PING_COUNT)

    # Create diagnostics instance
    diagnostics = NetworkDiagnostics(
        dns_server=dns_server if dns_server != "auto" else None,
        ping_count=ping_count,
    )

    async def async_update_data() -> NetworkDiagnosticsResult:
        """Fetch data from network diagnostics."""
        try:
            return await diagnostics.run_diagnostics()
        except Exception as err:
            raise UpdateFailed(f"Error running diagnostics: {err}") from err

    coordinator: DataUpdateCoordinator[NetworkDiagnosticsResult] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "diagnostics": diagnostics,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
