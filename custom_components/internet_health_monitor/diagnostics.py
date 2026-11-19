"""Diagnostics download for Internet Health Monitor."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import VERSION
from .coordinator import STORAGE_KEY, InternetHealthConfigEntry


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
        "usage": coordinator.usage.totals.to_dict(),
        "speed_test": (
            {
                "backend": data.speed_test.backend,
                "data_limit_mb": data.speed_test.data_limit_mb,
                "daily_limit": data.speed_test.daily_limit,
                "storage_key": STORAGE_KEY,
                "last_result": data.speed_test.data.to_dict() if data.speed_test.data else None,
            }
            if data.speed_test
            else None
        ),
    }
