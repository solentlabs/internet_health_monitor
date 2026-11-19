"""Coordinator and runtime data for Internet Health Monitor."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics, NetworkDiagnosticsResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Fixed poll interval (HA quality scale: appropriate-polling). Users who want
# another interval disable polling and call homeassistant.update_entity from
# an automation (README.md § Polling).
SCAN_INTERVAL = timedelta(seconds=60)


@dataclass
class InternetHealthRuntimeData:
    """What one config entry holds while loaded."""

    coordinator: InternetHealthCoordinator
    diagnostics: NetworkDiagnostics
    enable_gateway: bool
    enable_dns: bool


type InternetHealthConfigEntry = ConfigEntry[InternetHealthRuntimeData]


class InternetHealthCoordinator(DataUpdateCoordinator[NetworkDiagnosticsResult]):
    """Runs one diagnostics poll per interval."""

    config_entry: InternetHealthConfigEntry

    def __init__(self, hass: HomeAssistant, entry: InternetHealthConfigEntry, diagnostics: NetworkDiagnostics) -> None:
        """Poll the given diagnostics every SCAN_INTERVAL."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.diagnostics = diagnostics

    async def _async_update_data(self) -> NetworkDiagnosticsResult:
        """Run one poll; a failure marks entities unavailable until the next success."""
        try:
            return await self.diagnostics.run_diagnostics()
        except Exception as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
