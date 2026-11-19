"""Usage totals: what IHM has sent since install, as diagnostic sensors (README.md § Usage Totals)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.internet_health_monitor.const import DOMAIN
from custom_components.internet_health_monitor.usage import STORAGE_KEY, UsageTotals
from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics, ProbeCounts
from solentlabs.internet_health_monitor_core.speed_test import SpeedTestError, SpeedTestResult

from .conftest import SetupEntry, entity_id, make_result

RESULT = SpeedTestResult("cloudflare", "speed.cloudflare.com", 100.0, 20.0, 10.0, 30.0, 40.0, 80.3, 1.0, 50.1, 30.2)

# ┌──────────────────────────────┬──────────────┬────────────────────┐
# │ sensor key                   │ unit         │ device class       │
# ├──────────────────────────────┼──────────────┼────────────────────┤
# │ usage_pings                  │ none         │ none               │
# │ usage_traceroutes            │ none         │ none               │
# │ usage_dns_queries            │ none         │ none               │
# │ usage_speed_tests            │ none         │ none               │
# │ usage_downloaded             │ MB           │ data size          │
# │ usage_uploaded               │ MB           │ data size          │
# └──────────────────────────────┴──────────────┴────────────────────┘
# fmt: off
SENSOR_CASES: list[tuple[str, str | None, SensorDeviceClass | None]] = [
    ("usage_pings",       None, None),
    ("usage_traceroutes", None, None),
    ("usage_dns_queries", None, None),
    ("usage_speed_tests", None, None),
    ("usage_downloaded",  "MB", SensorDeviceClass.DATA_SIZE),
    ("usage_uploaded",    "MB", SensorDeviceClass.DATA_SIZE),
]
# fmt: on


@pytest.mark.parametrize("key,unit,device_class", SENSOR_CASES, ids=[c[0] for c in SENSOR_CASES])
async def test_usage_sensors_are_diagnostic_totals_off_by_default(
    hass: HomeAssistant, setup_entry: SetupEntry, key: str, unit: str | None, device_class: SensorDeviceClass | None
) -> None:
    """Each total is a diagnostic, ever-increasing sensor, disabled until the user enables it."""
    entry = await setup_entry()
    entity = er.async_get(hass).async_get(entity_id(hass, "sensor", entry, key) or "")
    assert entity is not None
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entity.capabilities == {"state_class": SensorStateClass.TOTAL_INCREASING}
    assert (entity.unit_of_measurement, entity.original_device_class) == (unit, device_class)


async def _enabled(hass: HomeAssistant, setup_entry: SetupEntry, **options: Any) -> MockConfigEntry:
    """Set up with every usage sensor enabled."""
    registry = er.async_get(hass)
    entry = await setup_entry(**options)
    for key, _, _ in SENSOR_CASES:
        registry.async_update_entity(entity_id(hass, "sensor", entry, key) or "", disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _value(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    """A usage sensor's state."""
    state = hass.states.get(entity_id(hass, "sensor", entry, key) or "")
    assert state is not None
    return state.state


async def test_probe_totals_follow_core_and_survive_reload(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Totals add Core's counts to what was stored, so a reload (new Core instance) loses nothing."""
    entry = await _enabled(hass, setup_entry)
    entry.runtime_data.diagnostics.counts = ProbeCounts(pings=12, traceroutes=1, dns_queries=5)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert (_value(hass, entry, "usage_pings"), _value(hass, entry, "usage_dns_queries")) == ("12", "5")

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    entry.runtime_data.diagnostics.counts = ProbeCounts(pings=3)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert (_value(hass, entry, "usage_pings"), _value(hass, entry, "usage_traceroutes")) == ("15", "1")


async def test_quick_checks_add_to_totals_at_once(
    hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """A quick check between polls (ADR-012) shows in the totals when it runs, not at the next poll."""
    entry = await _enabled(hass, setup_entry)
    diagnostics = entry.runtime_data.diagnostics
    diagnostics.counts = ProbeCounts(pings=10)

    async def one_ping() -> bool:
        diagnostics.counts.pings += 1
        return False

    with patch.object(NetworkDiagnostics, "check_gateway", side_effect=one_ping):
        poll.return_value = make_result(gateway_reachable=False)
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()
        assert _value(hass, entry, "usage_pings") == "10"
        polls = poll.await_count
        freezer.tick(5)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=0))
        await hass.async_block_till_done()
    assert _value(hass, entry, "usage_pings") == "11"
    assert poll.await_count == polls  # no poll ran: the quick check alone updated the sensor


async def test_speed_tests_add_runs_and_data(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Each accepted speed test counts once; completed ones add their downloaded and uploaded MB."""
    entry = await _enabled(hass, setup_entry, speed_test_backend="cloudflare")
    button = entity_id(hass, "button", entry, "run_speed_test")
    user = await hass.auth.async_create_user("Person", group_ids=["system-admin"])
    with patch("custom_components.internet_health_monitor.coordinator.run_speed_test", AsyncMock(return_value=RESULT)):
        for _ in range(2):
            await hass.services.async_call(
                "button", "press", {"entity_id": button}, blocking=True, context=Context(user_id=user.id)
            )
    await hass.async_block_till_done()
    assert _value(hass, entry, "usage_speed_tests") == "2"
    assert float(_value(hass, entry, "usage_downloaded")) == pytest.approx(100.2)
    assert float(_value(hass, entry, "usage_uploaded")) == pytest.approx(60.4)


async def test_totals_stored_and_removed_with_entry(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_storage: dict[str, Any]
) -> None:
    """Totals are saved on unload and deleted when the integration is removed."""
    entry = await setup_entry()
    entry.runtime_data.diagnostics.counts = ProbeCounts(pings=7)
    await entry.runtime_data.coordinator.async_refresh()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[STORAGE_KEY]["data"]["pings"] == 7
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert STORAGE_KEY not in hass_storage


def test_totals_shape() -> None:
    """Totals start at zero and are plain data."""
    assert UsageTotals().to_dict() == {
        "pings": 0,
        "traceroutes": 0,
        "dns_queries": 0,
        "speed_tests": 0,
        "downloaded_mb": 0.0,
        "uploaded_mb": 0.0,
    }
    assert DOMAIN in STORAGE_KEY


async def test_failed_speed_test_still_adds_its_data(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Data a failed test moved counts too: the ISP sees it either way."""
    entry = await _enabled(hass, setup_entry, speed_test_backend="cloudflare")
    button = entity_id(hass, "button", entry, "run_speed_test")
    user = await hass.auth.async_create_user("Person", group_ids=["system-admin"])
    failure = SpeedTestError("upload refused", downloaded_mb=40.5, uploaded_mb=0.3)
    with (
        patch("custom_components.internet_health_monitor.coordinator.run_speed_test", AsyncMock(side_effect=failure)),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "button", "press", {"entity_id": button}, blocking=True, context=Context(user_id=user.id)
        )
    await hass.async_block_till_done()
    assert (_value(hass, entry, "usage_downloaded"), _value(hass, entry, "usage_uploaded")) == ("40.5", "0.3")
    assert _value(hass, entry, "usage_speed_tests") == "1"
