"""Usage totals: what IHM has sent since install, as diagnostic sensors (README.md § Usage Totals)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.internet_health_monitor.const import CONF_USAGE_TOTALS, DOMAIN
from custom_components.internet_health_monitor.usage import STORAGE_KEY, UsageTotals
from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics, ProbeCounts
from solentlabs.internet_health_monitor_core.speed_test import SpeedTestError, SpeedTestResult

from .conftest import SetupEntry, entity_id, make_result, set_options

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


# registered by an older build as -> after setup with Usage totals on
# fmt: off
UPGRADE_CASES: list[tuple[str, er.RegistryEntryDisabler | None]] = [
    ("hidden by IHM",  None),                            # shown now
    ("hidden by user", er.RegistryEntryDisabler.USER),   # the user's choice stays
]
# fmt: on


@pytest.mark.parametrize("key,unit,device_class", SENSOR_CASES, ids=[c[0] for c in SENSOR_CASES])
async def test_usage_sensors_are_diagnostic_totals(
    hass: HomeAssistant, setup_entry: SetupEntry, key: str, unit: str | None, device_class: SensorDeviceClass | None
) -> None:
    """With Usage totals on, each total is an enabled diagnostic sensor with no state_class: no long-term statistics."""
    entry = await setup_entry(**{CONF_USAGE_TOTALS: True})
    entity = er.async_get(hass).async_get(entity_id(hass, "sensor", entry, key) or "")
    assert entity is not None
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.disabled_by is None
    assert entity.capabilities is None
    assert (entity.unit_of_measurement, entity.original_device_class) == (unit, device_class)


async def _enabled(hass: HomeAssistant, setup_entry: SetupEntry, **options: Any) -> MockConfigEntry:
    """Set up with Usage totals on."""
    return await setup_entry(**{CONF_USAGE_TOTALS: True}, **options)


async def test_usage_sensors_follow_the_option(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Off by default: no usage sensors. Turning it off removes them; counting goes on either way."""
    entry = await setup_entry()
    assert all(entity_id(hass, "sensor", entry, key) is None for key, _, _ in SENSOR_CASES)
    entry.runtime_data.diagnostics.counts = ProbeCounts(pings=4)
    await entry.runtime_data.coordinator.async_refresh()

    await set_options(hass, entry, {**entry.options, CONF_USAGE_TOTALS: True})
    entry.runtime_data.diagnostics.counts = ProbeCounts(pings=1)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert _value(hass, entry, "usage_pings") == "5"

    await set_options(hass, entry, {**entry.options, CONF_USAGE_TOTALS: False})
    assert all(entity_id(hass, "sensor", entry, key) is None for key, _, _ in SENSOR_CASES)


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


@pytest.mark.parametrize(("description", "expected"), UPGRADE_CASES, ids=[c[0] for c in UPGRADE_CASES])
async def test_usage_sensors_hidden_by_older_build_are_shown(
    hass: HomeAssistant, poll: AsyncMock, description: str, expected: er.RegistryEntryDisabler | None
) -> None:
    """Usage sensors an older build registered hidden show once Usage totals is on; ones a user hid stay hidden."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, options={CONF_USAGE_TOTALS: True})
    entry.add_to_hass(hass)
    disabler = er.RegistryEntryDisabler.USER if expected else er.RegistryEntryDisabler.INTEGRATION
    old = er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, f"{entry.entry_id}_usage_pings", config_entry=entry, disabled_by=disabler
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    now = er.async_get(hass).async_get(old.entity_id)
    assert now is not None  # same entity id, so its history carries over
    assert now.disabled_by is expected
    assert (hass.states.get(old.entity_id) is not None) is (expected is None)  # shown in this setup, no restart


async def test_probe_save_deadline_does_not_slide(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Polls every minute keep one save deadline (HA's delayed save would slide it forever), then start a new one."""
    entry = await setup_entry()
    usage = entry.runtime_data.coordinator.usage
    usage._save_at = 0.0  # noqa: SLF001  # forget setup's deadline, set on the real clock
    with (
        patch("custom_components.internet_health_monitor.usage.monotonic") as clock,
        patch.object(usage._store, "async_delay_save") as delay_save,  # noqa: SLF001
    ):
        for minute in range(7):
            clock.return_value = 1000.0 + 60 * minute
            usage.add_probes(ProbeCounts(pings=minute))
    delays = [call.args[1] for call in delay_save.call_args_list]
    # A save due at 1300 for every call through minute 4; from minute 5 (1300) a new one, due at 1600.
    assert delays == [300.0, 240.0, 180.0, 120.0, 60.0, 300.0, 240.0]


async def test_speed_test_data_saved_at_once(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_storage: dict[str, Any]
) -> None:
    """A speed test's runs and data are written right away, not after a delay a restart can cut short."""
    entry = await setup_entry(speed_test_backend="cloudflare", speed_test_automatic=False)
    user = await hass.auth.async_create_user("Person", group_ids=["system-admin"])
    with patch("custom_components.internet_health_monitor.coordinator.run_speed_test", AsyncMock(return_value=RESULT)):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id(hass, "button", entry, "run_speed_test")},
            blocking=True,
            context=Context(user_id=user.id),
        )
    await hass.async_block_till_done()
    stored = hass_storage[STORAGE_KEY]["data"]
    assert (stored["speed_tests"], stored["downloaded_mb"], stored["uploaded_mb"]) == (1, 50.1, 30.2)
