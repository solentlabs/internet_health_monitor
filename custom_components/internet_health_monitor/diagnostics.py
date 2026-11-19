"""Diagnostics download for Internet Health Monitor."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import VERSION
from .coordinator import InternetHealthConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: InternetHealthConfigEntry) -> dict[str, Any]:
    """Return settings, poll state, the latest result and what was detected."""
    data = entry.runtime_data
    coordinator = data.coordinator
    return {
        "version": VERSION,
        "options": dict(entry.options),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
        },
        "result": coordinator.data.to_dict() if coordinator.data else None,
        "detection_state": data.diagnostics.detection_state(),
    }
