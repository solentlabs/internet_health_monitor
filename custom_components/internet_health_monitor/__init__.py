"""Internet Health Monitor: gateway, hop and DNS health for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import issue_registry as ir

from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics, NetworkDiagnosticsConfig
from solentlabs.internet_health_monitor_core.platforms import UnsupportedPlatformError
from solentlabs.internet_health_monitor_core.platforms.linux import OPTIONAL_TOOLS

from .const import (
    CONF_DNS_SERVER,
    CONF_ENABLE_DNS_MONITORING,
    CONF_ENABLE_GATEWAY_MONITORING,
    CONF_HOP_OWNERSHIP,
    CONF_PING_COUNT,
    DEFAULT_DNS_SERVER,
    DEFAULT_PING_COUNT,
    DOMAIN,
    NAME,
    TROUBLESHOOTING_URL,
    VERSION,
)
from .coordinator import InternetHealthConfigEntry, InternetHealthCoordinator, InternetHealthRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: InternetHealthConfigEntry) -> bool:
    """Set up from a config entry; fail clearly if this host cannot measure anything."""
    _LOGGER.info("%s version %s is starting", NAME, VERSION)
    options = entry.options
    config = NetworkDiagnosticsConfig(
        ping_count=options.get(CONF_PING_COUNT, DEFAULT_PING_COUNT),
        dns_server=options.get(CONF_DNS_SERVER, DEFAULT_DNS_SERVER),
        hop_ownership=options.get(CONF_HOP_OWNERSHIP, False),
    )

    try:
        diagnostics = NetworkDiagnostics(config=config)
    except UnsupportedPlatformError as err:
        raise ConfigEntryError(translation_domain=DOMAIN, translation_key="unsupported_platform") from err

    missing = await hass.async_add_executor_job(diagnostics.platform.missing_tools)
    if missing:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="missing_tools",
            translation_placeholders={"tools": ", ".join(missing)},
        )

    optional_missing = await hass.async_add_executor_job(diagnostics.platform.missing_optional_tools)
    _sync_missing_tool_issues(hass, optional_missing)

    coordinator = InternetHealthCoordinator(hass, entry, diagnostics)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = InternetHealthRuntimeData(
        coordinator=coordinator,
        diagnostics=diagnostics,
        enable_gateway=options.get(CONF_ENABLE_GATEWAY_MONITORING, True),
        enable_dns=options.get(CONF_ENABLE_DNS_MONITORING, True),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options_change))
    return True


def _sync_missing_tool_issues(hass: HomeAssistant, missing: list[str]) -> None:
    """Raise a repair issue for each missing optional tool; clear it once installed."""
    for tool in OPTIONAL_TOOLS:
        issue_id = f"{tool}_missing"
        if tool in missing:
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=issue_id,
                learn_more_url=TROUBLESHOOTING_URL,
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_remove_entry(hass: HomeAssistant, entry: InternetHealthConfigEntry) -> None:
    """Clear this integration's repair issues when it is removed."""
    for tool in OPTIONAL_TOOLS:
        ir.async_delete_issue(hass, DOMAIN, f"{tool}_missing")


async def _async_reload_on_options_change(hass: HomeAssistant, entry: InternetHealthConfigEntry) -> None:
    """Apply changed options by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: InternetHealthConfigEntry) -> bool:
    """Unload a config entry; runtime_data is released by HA."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
