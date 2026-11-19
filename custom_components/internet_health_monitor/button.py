"""Button platform: refresh now, reset detected network details, run a speed test."""

from __future__ import annotations

from typing import override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import InternetHealthConfigEntry, InternetHealthCoordinator, SpeedTestCoordinator
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

RUN_SPEED_TEST = ButtonEntityDescription(key="run_speed_test", translation_key="run_speed_test")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InternetHealthConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the buttons."""
    coordinator = entry.runtime_data.coordinator
    buttons: list[ButtonEntity] = [RefreshButton(coordinator, REFRESH), ResetCacheButton(coordinator, RESET_CACHE)]
    if speed_test := entry.runtime_data.speed_test:
        buttons.append(RunSpeedTestButton(speed_test, RUN_SPEED_TEST))
    async_add_entities(buttons)


class _PollButton(InternetHealthEntity[InternetHealthCoordinator], ButtonEntity):
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

    @override
    async def async_press(self) -> None:
        """Poll now."""
        await self._poll()


class ResetCacheButton(_PollButton):
    """Forget the detected gateway, hops and hostnames, then detect them again."""

    @override
    async def async_press(self) -> None:
        """Reset detection and poll."""
        self.coordinator.diagnostics.reset_all()
        await self._poll()


class RunSpeedTestButton(InternetHealthEntity[SpeedTestCoordinator], ButtonEntity):
    """Run one speed test now; automations press it to schedule tests (README.md § Speed Testing)."""

    def __init__(self, coordinator: SpeedTestCoordinator, description: ButtonEntityDescription) -> None:
        """Attach the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @override
    @property
    def available(self) -> bool:
        """Stays available after a failed test, so the user can try again."""
        return True

    @override
    async def async_press(self) -> None:
        """Run a test; a press with no user behind it (automation, script) counts as automated."""
        person = self._context is not None and self._context.user_id is not None
        await self.coordinator.async_run(automated=not person)
