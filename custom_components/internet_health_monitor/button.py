"""Button platform: refresh now, and reset detected network details."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import InternetHealthConfigEntry, InternetHealthCoordinator
from .entity import InternetHealthEntity

# Presses run one poll at a time.
PARALLEL_UPDATES = 1

REFRESH = ButtonEntityDescription(
    key="refresh_diagnostics", translation_key="refresh_diagnostics", entity_category=EntityCategory.DIAGNOSTIC
)
RESET_CACHE = ButtonEntityDescription(
    key="reset_cache",
    translation_key="reset_cache",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InternetHealthConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the buttons."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([RefreshButton(coordinator, REFRESH), ResetCacheButton(coordinator, RESET_CACHE)])


class _PollButton(InternetHealthEntity, ButtonEntity):
    """A button whose press ends in a poll that must succeed."""

    def __init__(self, coordinator: InternetHealthCoordinator, description: ButtonEntityDescription) -> None:
        """Attach the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def _poll(self) -> None:
        """Poll now; raise a translated error if the poll fails."""
        await self.coordinator.async_refresh()
        if not self.coordinator.last_update_success:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="refresh_failed")


class RefreshButton(_PollButton):
    """Run a poll now instead of waiting for the next one."""

    async def async_press(self) -> None:
        """Poll now."""
        await self._poll()


class ResetCacheButton(_PollButton):
    """Forget the detected gateway, hops and hostnames, then detect them again."""

    async def async_press(self) -> None:
        """Reset detection and poll."""
        self.coordinator.diagnostics.reset_all()
        await self._poll()
