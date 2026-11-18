"""Tests for Internet Health Monitor button platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.internet_health_monitor.button import (
    RefreshDiagnosticsButton,
    RefreshNetworkInfoButton,
    ResetCacheButton,
    async_setup_entry,
)
from custom_components.internet_health_monitor.const import DOMAIN, MANUFACTURER, NAME


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = Mock()
    entry.entry_id = "test_entry_id"
    return entry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock(spec=DataUpdateCoordinator)
    coordinator.data = Mock()
    coordinator.last_update_success = True
    coordinator.update_interval = timedelta(seconds=60)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_creates_buttons(self, mock_coordinator, mock_config_entry):
        """Test button platform setup creates expected buttons."""
        hass = Mock(spec=HomeAssistant)
        hass.data = {DOMAIN: {mock_config_entry.entry_id: {"coordinator": mock_coordinator}}}

        async_add_entities = Mock()

        await async_setup_entry(hass, mock_config_entry, async_add_entities)

        # Verify three buttons were added
        assert async_add_entities.call_count == 1
        added_entities = async_add_entities.call_args[0][0]
        assert len(added_entities) == 3
        assert isinstance(added_entities[0], RefreshDiagnosticsButton)
        assert isinstance(added_entities[1], RefreshNetworkInfoButton)
        assert isinstance(added_entities[2], ResetCacheButton)


class TestInternetHealthButtonBase:
    """Test the base button class."""

    def test_base_class_attributes(self, mock_coordinator, mock_config_entry):
        """Test base class sets correct attributes."""
        button = RefreshDiagnosticsButton(mock_coordinator, mock_config_entry)

        assert button._attr_has_entity_name is True
        assert button._attr_entity_category == EntityCategory.CONFIG

    def test_device_info(self, mock_coordinator, mock_config_entry):
        """Test device info is set correctly."""
        button = RefreshDiagnosticsButton(mock_coordinator, mock_config_entry)

        assert button._attr_device_info["identifiers"] == {(DOMAIN, "test_entry_id")}
        assert button._attr_device_info["name"] == NAME
        assert button._attr_device_info["manufacturer"] == MANUFACTURER
        assert button._attr_device_info["model"] == NAME


class TestRefreshDiagnosticsButton:
    """Test the refresh diagnostics button."""

    def test_initialization(self, mock_coordinator, mock_config_entry):
        """Test button initialization."""
        button = RefreshDiagnosticsButton(mock_coordinator, mock_config_entry)

        assert button._attr_name == "Refresh Diagnostics"
        assert button._attr_unique_id == "test_entry_id_refresh_diagnostics"
        assert button._attr_icon == "mdi:refresh"
        assert button._attr_entity_category == EntityCategory.CONFIG

    @pytest.mark.asyncio
    async def test_press_triggers_refresh(self, mock_coordinator, mock_config_entry):
        """Test button press triggers coordinator refresh."""
        button = RefreshDiagnosticsButton(mock_coordinator, mock_config_entry)

        await button.async_press()

        # Verify coordinator refresh was called
        mock_coordinator.async_request_refresh.assert_called_once()


class TestRefreshNetworkInfoButton:
    """Test the refresh network info button."""

    def test_initialization(self, mock_coordinator, mock_config_entry):
        """Test button initialization."""
        button = RefreshNetworkInfoButton(mock_coordinator, mock_config_entry)

        assert button._attr_name == "Refresh Network Info"
        assert button._attr_unique_id == "test_entry_id_refresh_network_info"
        assert button._attr_icon == "mdi:earth-arrow-right"
        assert button._attr_entity_category == EntityCategory.DIAGNOSTIC

    @pytest.mark.asyncio
    async def test_press_resets_metadata_and_refreshes(self, mock_coordinator, mock_config_entry):
        """Test button press resets metadata and triggers refresh."""
        # Setup mock diagnostics instance
        mock_diagnostics = Mock()
        mock_diagnostics.reset_metadata = Mock()

        hass = Mock(spec=HomeAssistant)
        hass.data = {
            DOMAIN: {
                mock_config_entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "diagnostics": mock_diagnostics,
                }
            }
        }

        button = RefreshNetworkInfoButton(mock_coordinator, mock_config_entry)
        button.hass = hass
        button._entry = mock_config_entry

        await button.async_press()

        # Verify metadata reset was called
        mock_diagnostics.reset_metadata.assert_called_once()

        # Verify coordinator refresh was called
        mock_coordinator.async_request_refresh.assert_called_once()


class TestResetCacheButton:
    """Test the reset cache button."""

    def test_initialization(self, mock_coordinator, mock_config_entry):
        """Test button initialization."""
        button = ResetCacheButton(mock_coordinator, mock_config_entry)

        assert button._attr_name == "Reset Network Cache"
        assert button._attr_unique_id == "test_entry_id_reset_cache"
        assert button._attr_icon == "mdi:cached"
        assert button._attr_entity_category == EntityCategory.DIAGNOSTIC

    @pytest.mark.asyncio
    async def test_press_resets_cache_and_refreshes(self, mock_coordinator, mock_config_entry):
        """Test button press resets cache and triggers refresh."""
        # Setup mock diagnostics instance
        mock_diagnostics = Mock()
        mock_diagnostics.reset_all = Mock()

        hass = Mock(spec=HomeAssistant)
        hass.data = {
            DOMAIN: {
                mock_config_entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "diagnostics": mock_diagnostics,
                }
            }
        }

        button = ResetCacheButton(mock_coordinator, mock_config_entry)
        button.hass = hass
        button._entry = mock_config_entry

        await button.async_press()

        # Verify diagnostics reset was called
        mock_diagnostics.reset_all.assert_called_once()

        # Verify coordinator refresh was called
        mock_coordinator.async_request_refresh.assert_called_once()


class TestButtonUniqueIds:
    """Test that buttons have correct unique IDs."""

    def test_refresh_button_unique_id(self, mock_coordinator, mock_config_entry):
        """Test refresh button has correct unique ID."""
        button = RefreshDiagnosticsButton(mock_coordinator, mock_config_entry)
        assert button._attr_unique_id == "test_entry_id_refresh_diagnostics"

    def test_refresh_network_info_button_unique_id(self, mock_coordinator, mock_config_entry):
        """Test refresh network info button has correct unique ID."""
        button = RefreshNetworkInfoButton(mock_coordinator, mock_config_entry)
        assert button._attr_unique_id == "test_entry_id_refresh_network_info"

    def test_reset_button_unique_id(self, mock_coordinator, mock_config_entry):
        """Test reset button has correct unique ID."""
        button = ResetCacheButton(mock_coordinator, mock_config_entry)
        assert button._attr_unique_id == "test_entry_id_reset_cache"

    def test_unique_ids_are_unique(self, mock_coordinator, mock_config_entry):
        """Test all button unique IDs are different."""
        refresh_button = RefreshDiagnosticsButton(mock_coordinator, mock_config_entry)
        refresh_network_button = RefreshNetworkInfoButton(mock_coordinator, mock_config_entry)
        reset_button = ResetCacheButton(mock_coordinator, mock_config_entry)

        unique_ids = {
            refresh_button._attr_unique_id,
            refresh_network_button._attr_unique_id,
            reset_button._attr_unique_id,
        }
        assert len(unique_ids) == 3


class TestButtonIcons:
    """Test button icons."""

    def test_refresh_button_icon(self, mock_coordinator, mock_config_entry):
        """Test refresh button icon."""
        button = RefreshDiagnosticsButton(mock_coordinator, mock_config_entry)
        assert button._attr_icon == "mdi:refresh"

    def test_refresh_network_info_button_icon(self, mock_coordinator, mock_config_entry):
        """Test refresh network info button icon."""
        button = RefreshNetworkInfoButton(mock_coordinator, mock_config_entry)
        assert button._attr_icon == "mdi:earth-arrow-right"

    def test_reset_button_icon(self, mock_coordinator, mock_config_entry):
        """Test reset button icon."""
        button = ResetCacheButton(mock_coordinator, mock_config_entry)
        assert button._attr_icon == "mdi:cached"


class TestButtonEntityCategories:
    """Test button entity categories."""

    def test_refresh_button_category(self, mock_coordinator, mock_config_entry):
        """Test refresh button entity category."""
        button = RefreshDiagnosticsButton(mock_coordinator, mock_config_entry)
        assert button._attr_entity_category == EntityCategory.CONFIG

    def test_refresh_network_info_button_category(self, mock_coordinator, mock_config_entry):
        """Test refresh network info button entity category."""
        button = RefreshNetworkInfoButton(mock_coordinator, mock_config_entry)
        assert button._attr_entity_category == EntityCategory.DIAGNOSTIC

    def test_reset_button_category(self, mock_coordinator, mock_config_entry):
        """Test reset button entity category."""
        button = ResetCacheButton(mock_coordinator, mock_config_entry)
        assert button._attr_entity_category == EntityCategory.DIAGNOSTIC
