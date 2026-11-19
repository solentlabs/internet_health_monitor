"""Base entity for Internet Health Monitor."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_NAME, DOMAIN, MANUFACTURER, VERSION
from .coordinator import InternetHealthCoordinator, SpeedTestCoordinator


class InternetHealthEntity[C: InternetHealthCoordinator | SpeedTestCoordinator](CoordinatorEntity[C]):
    """Shared unique id and device for every Internet Health Monitor entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: C, key: str) -> None:
        """Attach the entity to the entry's single service device."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        coordinator.config_entry.runtime_data.unique_ids.add(self._attr_unique_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=DEVICE_NAME,
            manufacturer=MANUFACTURER,
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )
