"""Tests for the Refresh and Reset network cache buttons."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.button import (  # public in HA, not in its __all__
    DOMAIN as BUTTON_DOMAIN,  # pyright: ignore[reportPrivateImportUsage]
    SERVICE_PRESS,  # pyright: ignore[reportPrivateImportUsage]
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics

from .conftest import SetupEntry, entity_id


async def _press(hass: HomeAssistant, button: str) -> None:
    """Press a button through HA's service, as the UI does."""
    await hass.services.async_call(BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: button}, blocking=True)


async def test_refresh_polls_now(hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock) -> None:
    """Refresh runs a poll immediately."""
    entry = await setup_entry()
    before = poll.await_count
    await _press(hass, entity_id(hass, "button", entry, "refresh_diagnostics") or "")
    assert poll.await_count == before + 1


async def test_failed_refresh_raises(hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock) -> None:
    """A press whose poll fails tells the user instead of silently doing nothing."""
    entry = await setup_entry()
    poll.side_effect = OSError("boom")
    with pytest.raises(HomeAssistantError):
        await _press(hass, entity_id(hass, "button", entry, "refresh_diagnostics") or "")


async def test_reset_cache_is_disabled_by_default(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Reset network cache is a troubleshooting tool, hidden until enabled."""
    entry = await setup_entry()
    button = entity_id(hass, "button", entry, "reset_cache")
    assert button is not None
    registry_entry = er.async_get(hass).async_get(button)
    assert registry_entry is not None
    assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_reset_cache_redetects(hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock) -> None:
    """Once enabled, Reset network cache clears detection and polls."""
    entry = await setup_entry()
    button = entity_id(hass, "button", entry, "reset_cache") or ""
    er.async_get(hass).async_update_entity(button, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(NetworkDiagnostics, "reset_all") as reset:
        before = poll.await_count
        await _press(hass, button)
    reset.assert_called_once()
    assert poll.await_count == before + 1
