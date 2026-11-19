"""Internet Health Monitor - Home Assistant Integration.

A Solent Labs integration for network health monitoring including:
- Gateway latency and reachability
- 3-hop network path monitoring (gateway, ISP, backbone)
- Per-hop jitter (latency variance)
- Packet loss percentage
- DNS resolution timing
- Reverse DNS names for detected hops
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics, NetworkDiagnosticsConfig

from .const import (
    CONF_DNS_SERVER,
    CONF_ENABLE_DNS_MONITORING,
    CONF_ENABLE_GATEWAY_MONITORING,
    CONF_PING_COUNT,
    CONF_SCAN_INTERVAL,
    DEFAULT_DNS_SERVER,
    DEFAULT_PING_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NAME,
    VERSION,
)

if TYPE_CHECKING:
    from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnosticsResult

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Internet Health Monitor from a config entry."""
    _LOGGER.info("%s version %s is starting", NAME, VERSION)

    # Get configuration options
    options = entry.options
    scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    dns_server = options.get(CONF_DNS_SERVER, DEFAULT_DNS_SERVER)
    ping_count = options.get(CONF_PING_COUNT, DEFAULT_PING_COUNT)
    enable_gateway = options.get(CONF_ENABLE_GATEWAY_MONITORING, True)
    enable_dns = options.get(CONF_ENABLE_DNS_MONITORING, True)

    _LOGGER.debug(
        "Configuration: gateway=%s, dns=%s, interval=%s, ping_count=%s",
        enable_gateway,
        enable_dns,
        scan_interval,
        ping_count,
    )

    # Create diagnostics config with options
    config = NetworkDiagnosticsConfig(
        ping_count=ping_count,
        dns_server=dns_server if dns_server != "auto" else "auto",
    )

    # Create diagnostics instance
    diagnostics = NetworkDiagnostics(config=config)

    # Store monitoring flags for sensors to use
    monitoring_config = {
        "enable_gateway": enable_gateway,
        "enable_dns": enable_dns,
    }

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

    # Store coordinator and config
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "diagnostics": diagnostics,
        "config": monitoring_config,
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
