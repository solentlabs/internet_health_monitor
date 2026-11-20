"""Internet Health Monitor: gateway, hop and DNS health for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.helpers.typing import ConfigType

from solentlabs.internet_health_monitor_core import timing
from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics, NetworkDiagnosticsConfig
from solentlabs.internet_health_monitor_core.platforms import UnsupportedPlatformError
from solentlabs.internet_health_monitor_core.platforms.linux import OPTIONAL_TOOLS

from .card import async_register_card
from .const import (
    CONF_DNS_SERVER,
    CONF_ENABLE_DNS_MONITORING,
    CONF_ENABLE_GATEWAY_MONITORING,
    CONF_HOP_OWNERSHIP,
    CONF_LONG_TERM_STATISTICS,
    CONF_MLAB_CONSENT,
    CONF_PING_COUNT,
    CONF_SPEED_TEST_AUTOMATIC,
    CONF_SPEED_TEST_BACKEND,
    CONF_SPEED_TEST_BUDGET,
    CONF_SPEED_TEST_DAILY_LIMIT,
    CONF_SPEED_TEST_DATA_LIMIT,
    CONF_USAGE_TOTALS,
    DEFAULT_DNS_SERVER,
    DEFAULT_PING_COUNT,
    DNS_SERVERS,
    DOMAIN,
    NAME,
    SPEED_TEST_OFF,
    TROUBLESHOOTING_URL,
    VERSION,
)
from .coordinator import (
    STORAGE_KEY,
    InternetHealthConfigEntry,
    InternetHealthCoordinator,
    InternetHealthRuntimeData,
    ReachabilityTarget,
    SpeedTestCoordinator,
)
from .services import async_setup_services
from .usage import (
    STORAGE_KEY as USAGE_STORAGE_KEY,
    UsageTracker,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions and the dashboard card, once per HA start."""
    async_setup_services(hass)
    await async_register_card(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: InternetHealthConfigEntry) -> bool:
    """Bring an older entry up to date before setup.

    1.1 -> 1.2: entries from before the Long-term statistics option already
    built statistics, so they keep it on; turning it off would raise one HA
    warning per sensor (ADR-013). New entries start off. HA itself refuses an
    entry from a newer major version before calling this.
    """
    if entry.minor_version < 2:
        options = {CONF_LONG_TERM_STATISTICS: True, **entry.options}
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: InternetHealthConfigEntry) -> bool:
    """Set up from a config entry; fail clearly if this host cannot measure anything."""
    _LOGGER.info("%s version %s is starting", NAME, VERSION)
    options = entry.options
    config = NetworkDiagnosticsConfig(
        ping_count=options.get(CONF_PING_COUNT, DEFAULT_PING_COUNT),
        dns_server=dns_server_address(options.get(CONF_DNS_SERVER, DEFAULT_DNS_SERVER)),
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

    usage = UsageTracker(hass)
    await usage.async_load()
    targets: list[ReachabilityTarget] = []
    if options.get(CONF_ENABLE_GATEWAY_MONITORING, True):
        targets.append("gateway")
    if options.get(CONF_ENABLE_DNS_MONITORING, True):
        targets.append("internet")
    coordinator = InternetHealthCoordinator(hass, entry, diagnostics, usage, tuple(targets))
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = InternetHealthRuntimeData(
        coordinator=coordinator,
        diagnostics=diagnostics,
        enable_gateway=options.get(CONF_ENABLE_GATEWAY_MONITORING, True),
        enable_dns=options.get(CONF_ENABLE_DNS_MONITORING, True),
        usage_totals=options.get(CONF_USAGE_TOTALS, False),
        long_term_statistics=options.get(CONF_LONG_TERM_STATISTICS, False),
        installation_type=(await async_get_system_info(hass))["installation_type"],
        speed_test=await _async_speed_test(hass, entry, usage),
    )
    _show_hidden_usage_sensors(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_stale_entities(hass, entry)
    return True


async def _async_speed_test(
    hass: HomeAssistant, entry: InternetHealthConfigEntry, usage: UsageTracker
) -> SpeedTestCoordinator | None:
    """The speed test runner, if the user chose a backend (and consented, for M-Lab); never runs here."""
    options = entry.options
    backend = options.get(CONF_SPEED_TEST_BACKEND, SPEED_TEST_OFF)
    if backend == SPEED_TEST_OFF or (backend == "mlab" and not options.get(CONF_MLAB_CONSENT)):
        return None
    coordinator = SpeedTestCoordinator(
        hass,
        entry,
        backend,
        data_limit_mb=options.get(CONF_SPEED_TEST_DATA_LIMIT, timing.SPEED_TEST_DATA_LIMIT_MB_DEFAULT),
        daily_limit=options.get(CONF_SPEED_TEST_DAILY_LIMIT, timing.SPEED_TEST_DAILY_DEFAULT),
        usage=usage,
        automatic=options.get(CONF_SPEED_TEST_AUTOMATIC, True),
        budget_gb=options.get(CONF_SPEED_TEST_BUDGET, timing.SPEED_TEST_BUDGET_GB_DEFAULT),
    )
    await coordinator.async_load()
    return coordinator


def _show_hidden_usage_sensors(hass: HomeAssistant, entry: InternetHealthConfigEntry) -> None:
    """Clear the hidden flag an older build gave usage sensors, so the Usage totals option alone decides.

    HA: entities an option controls are created or removed, not disabled by the
    integration. HA restores a removed entity's flag, so the flag is cleared
    (HA reloads the entry once, 30 s later). Ones a user hid stay hidden.
    """
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            entity.unique_id.startswith(f"{entry.entry_id}_usage_")
            and entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        ):
            registry.async_update_entity(entity.entity_id, disabled_by=None)


def _remove_stale_entities(hass: HomeAssistant, entry: InternetHealthConfigEntry) -> None:
    """Remove this entry's entities that the current options no longer create."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id not in entry.runtime_data.unique_ids:
            registry.async_remove(entity.entity_id)


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
    """Clear this integration's repair issues and stored speed test history when it is removed."""
    for tool in OPTIONAL_TOOLS:
        ir.async_delete_issue(hass, DOMAIN, f"{tool}_missing")
    await Store[dict[str, object]](hass, 1, STORAGE_KEY).async_remove()
    await Store[dict[str, object]](hass, 1, USAGE_STORAGE_KEY).async_remove()


def dns_server_address(choice: str) -> str:
    """The server for a DNS choice; a stored address (older entries) passes through."""
    return DNS_SERVERS.get(choice, choice)


async def async_unload_entry(hass: HomeAssistant, entry: InternetHealthConfigEntry) -> bool:
    """Unload a config entry, writing the usage totals first; runtime_data is released by HA."""
    await entry.runtime_data.coordinator.usage.async_save()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
