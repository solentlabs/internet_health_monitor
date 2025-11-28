"""Button platform for HA Network Diagnostics."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Network Diagnostics buttons."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([
        RefreshDiagnosticsButton(coordinator, entry),
        ResetCacheButton(coordinator, entry),
    ])


class NetworkDiagnosticsButtonBase(CoordinatorEntity, ButtonEntity):
    """Base class for network diagnostics buttons."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_category = EntityCategory.CONFIG

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Network Diagnostics",
            "manufacturer": "HA Network Diagnostics",
            "model": "Network Monitor",
        }


class RefreshDiagnosticsButton(NetworkDiagnosticsButtonBase):
    """Button to trigger immediate network diagnostics refresh."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the refresh button."""
        super().__init__(
            coordinator,
            entry,
            "refresh_diagnostics",
            "Refresh Diagnostics",
            "mdi:refresh",
        )

    async def async_press(self) -> None:
        """Handle button press - trigger immediate refresh."""
        _LOGGER.debug("Manual network diagnostics refresh triggered")
        await self.coordinator.async_request_refresh()


class ResetCacheButton(NetworkDiagnosticsButtonBase):
    """Button to reset cached gateway/ISP hop detection."""

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        """Initialize the reset button."""
        super().__init__(
            coordinator,
            entry,
            "reset_cache",
            "Reset Network Cache",
            "mdi:cached",
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle button press - reset cached network info."""
        _LOGGER.debug("Resetting network diagnostics cache")
        diagnostics = self.hass.data[DOMAIN][self._entry.entry_id]["diagnostics"]
        diagnostics.reset_all()
        await self.coordinator.async_request_refresh()
