"""Speed tests in HA: options and M-Lab consent, sensors, the button, automatic tests, limits and persistence."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.internet_health_monitor.config_flow import DEFAULTS
from custom_components.internet_health_monitor.const import (
    CONF_MLAB_CONSENT,
    CONF_SPEED_TEST_AUTOMATIC,
    CONF_SPEED_TEST_BACKEND,
    CONF_SPEED_TEST_BUDGET,
    CONF_SPEED_TEST_DAILY_LIMIT,
    CONF_SPEED_TEST_DATA_LIMIT,
    DOMAIN,
)
from custom_components.internet_health_monitor.coordinator import STORAGE_KEY, next_automatic_test
from custom_components.internet_health_monitor.diagnostics import async_get_config_entry_diagnostics
from solentlabs.internet_health_monitor_core.speed_test import DataLimit, SpeedTestError, SpeedTestResult

from .conftest import SetupEntry, entity_id, set_options

RESULT = SpeedTestResult(
    backend="cloudflare",
    server="speed.cloudflare.com",
    download_mbps=245.6,
    upload_mbps=11.2,
    idle_latency_ms=12.0,
    download_latency_ms=48.5,
    upload_latency_ms=310.0,
    data_used_mb=330.4,
    started_at=1_795_000_000.0,
    download_ended_by="time",
    upload_ended_by="data_limit",
    download_s=10.0,
    upload_s=6.2,
)
# Automatic tests are off unless a test is about them, so time moving never starts one by accident.
CLOUDFLARE = {CONF_SPEED_TEST_BACKEND: "cloudflare", CONF_SPEED_TEST_AUTOMATIC: False}
SPEED_SENSORS = [
    "speed_test_download",
    "speed_test_upload",
    "speed_test_idle_latency",
    "speed_test_download_latency",
    "speed_test_upload_latency",
    "speed_test_data_used",
    "speed_test_download_latency_increase",
    "speed_test_upload_latency_increase",
    "speed_test_bufferbloat_grade",
]


# Automatic test times (HA's test time zone is US/Pacific): now, the last automatic test, days
# between tests, random offset -> next test. The earliest night is the last test's plus the
# spacing, or tonight if that has passed; the test is at the offset into that night's 1 to 5 am.
# ┌──────────────┬──────────────────┬──────┬────────┬──────────────────┐
# │ now (local)  │ last test        │ days │ offset │ next test        │
# ├──────────────┼──────────────────┼──────┼────────┼──────────────────┤
# │ 11-19 00:30  │ none             │ 7    │ 3600   │ 11-19 02:00      │
# │ 11-19 02:30  │ none             │ 7    │ 3600   │ 11-20 02:00      │
# │ 11-19 02:30  │ none             │ 7    │ 7200   │ 11-19 03:00      │
# │ 11-19 12:00  │ none             │ 1    │ 0      │ 11-20 01:00      │
# │ 11-19 12:00  │ 11-19 03:00      │ 7    │ 0      │ 11-26 01:00      │
# │ 11-19 12:00  │ 11-19 03:00      │ 1    │ 14400  │ 11-20 05:00      │
# │ 11-19 12:00  │ 11-01 03:00      │ 7    │ 0      │ 11-20 01:00      │ overdue: next night
# │ 11-19 00:30  │ 11-12 04:00      │ 7    │ 3600   │ 11-19 02:00      │ due tonight
# └──────────────┴──────────────────┴──────┴────────┴──────────────────┘
# fmt: off
NEXT_CASES: list[tuple[str, str | None, int, int, str]] = [
    ("2026-11-19 00:30:00", None,                  7, 3600,  "2026-11-19 02:00:00"),
    ("2026-11-19 02:30:00", None,                  7, 3600,  "2026-11-20 02:00:00"),
    ("2026-11-19 02:30:00", None,                  7, 7200,  "2026-11-19 03:00:00"),
    ("2026-11-19 12:00:00", None,                  1, 0,     "2026-11-20 01:00:00"),
    ("2026-11-19 12:00:00", "2026-11-19 03:00:00", 7, 0,     "2026-11-26 01:00:00"),
    ("2026-11-19 12:00:00", "2026-11-19 03:00:00", 1, 14400, "2026-11-20 05:00:00"),
    ("2026-11-19 12:00:00", "2026-11-01 03:00:00", 7, 0,     "2026-11-20 01:00:00"),
    ("2026-11-19 00:30:00", "2026-11-12 04:00:00", 7, 3600,  "2026-11-19 02:00:00"),
]
# fmt: on


@pytest.fixture
def speed_test() -> Iterator[AsyncMock]:
    """Script Core's speed test; no test traffic is sent."""
    mock = AsyncMock(return_value=RESULT)
    with patch("custom_components.internet_health_monitor.coordinator.run_speed_test", mock):
        yield mock


async def _press(hass: HomeAssistant, entry: MockConfigEntry, *, by_person: bool = True) -> None:
    """Press Run speed test, as a person in the UI or as an automation (no user)."""
    button = entity_id(hass, "button", entry, "run_speed_test")
    assert button
    context = (
        Context(user_id=(await hass.auth.async_create_user("Person", group_ids=["system-admin"])).id)
        if by_person
        else Context()
    )
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True, context=context)


def _state(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    """A sensor's state."""
    state = hass.states.get(entity_id(hass, "sensor", entry, key) or "")
    assert state is not None
    return state.state


async def test_off_by_default_creates_nothing(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """With no backend chosen there are no speed test entities."""
    entry = await setup_entry()
    assert entity_id(hass, "button", entry, "run_speed_test") is None
    assert all(entity_id(hass, "sensor", entry, key) is None for key in SPEED_SENSORS)


async def test_never_runs_on_its_own(hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock) -> None:
    """With automatic tests off, setup and time passing never start a test; sensors read unknown until one runs."""
    entry = await setup_entry(**CLOUDFLARE)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=2))
    await hass.async_block_till_done()
    speed_test.assert_not_called()
    assert _state(hass, entry, "speed_test_download") == STATE_UNKNOWN


# ┌──────────────────────────────┬──────────┐
# │ sensor                       │ state    │
# ├──────────────────────────────┼──────────┤
# │ download                     │ 245.6    │
# │ upload                       │ 11.2     │
# │ idle latency                 │ 12.0     │
# │ download latency             │ 48.5     │
# │ upload latency               │ 310.0    │
# │ data used                    │ 330.4    │
# │ download latency increase    │ 36.5     │
# │ upload latency increase      │ 298.0    │
# │ bufferbloat grade            │ d (D)    │
# └──────────────────────────────┴──────────┘
# fmt: off
STATE_CASES: list[tuple[str, str]] = [
    ("speed_test_download",         "245.6"),
    ("speed_test_upload",           "11.2"),
    ("speed_test_idle_latency",     "12.0"),
    ("speed_test_download_latency", "48.5"),
    ("speed_test_upload_latency",   "310.0"),
    ("speed_test_data_used",        "330.4"),
    ("speed_test_download_latency_increase", "36.5"),
    ("speed_test_upload_latency_increase",   "298.0"),
    ("speed_test_bufferbloat_grade",         "d"),
]
# fmt: on


@pytest.mark.parametrize("key,expected", STATE_CASES)
async def test_press_runs_and_fills_sensors(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, key: str, expected: str
) -> None:
    """A press runs one test with the chosen backend and data limit, split evenly; each sensor shows its field."""
    entry = await setup_entry(**CLOUDFLARE, **{CONF_SPEED_TEST_DATA_LIMIT: 500})
    await _press(hass, entry)
    assert speed_test.call_args.args[0] == "cloudflare"
    assert speed_test.call_args.args[2] == DataLimit(250, 250)
    assert _state(hass, entry, key) == expected
    attrs = hass.states.get(entity_id(hass, "sensor", entry, key) or "")
    assert attrs is not None
    assert (attrs.attributes["backend"], attrs.attributes["server"]) == ("cloudflare", "speed.cloudflare.com")
    assert "tested_at" in attrs.attributes


# sensor -> (ended_by, duration_s) attributes: whether each direction ran its whole window.
# fmt: off
QUALITY_CASES: list[tuple[str, dict[str, Any]]] = [
    ("speed_test_download", {"ended_by": "time",       "duration_s": 10.0}),
    ("speed_test_upload",   {"ended_by": "data_limit", "duration_s": 6.2}),
]
# fmt: on


@pytest.mark.parametrize("key,expected", QUALITY_CASES)
async def test_throughput_says_what_ended_it(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, key: str, expected: dict[str, Any]
) -> None:
    """Download and upload say whether time or the data limit ended them, and after how long."""
    entry = await setup_entry(**CLOUDFLARE)
    await _press(hass, entry)
    state = hass.states.get(entity_id(hass, "sensor", entry, key) or "")
    assert state is not None
    assert {k: state.attributes[k] for k in expected} == expected


async def test_automatic_data_limit_follows_the_last_test(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """With the data limit at 0, the first test calibrates at 500 MB; later ones fit the last test's speeds."""
    entry = await setup_entry(**CLOUDFLARE, **{CONF_SPEED_TEST_DATA_LIMIT: 0})
    await _press(hass, entry)
    assert speed_test.call_args.args[2] == DataLimit(250, 250)
    await _press(hass, entry)  # 245.6 / 11.2 Mbit/s: 10 s each, plus 25%, upload at the 50 MB floor
    assert speed_test.call_args.args[2] == DataLimit(390, 50)


async def test_failed_test_is_visible(hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock) -> None:
    """A failure raises a translated error with the reason and makes the sensors unavailable, not stale."""
    entry = await setup_entry(**CLOUDFLARE)
    await _press(hass, entry)
    speed_test.side_effect = SpeedTestError("no LibreSpeed server answered")
    with pytest.raises(HomeAssistantError, match="no LibreSpeed server answered") as err:
        await _press(hass, entry)
    assert err.value.translation_key == "speed_test_failed"
    assert _state(hass, entry, "speed_test_download") == STATE_UNAVAILABLE


async def test_daily_limit(hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock) -> None:
    """Runs past the daily limit are refused without a test, and the last result stays."""
    entry = await setup_entry(**CLOUDFLARE, **{CONF_SPEED_TEST_DAILY_LIMIT: 2})
    await _press(hass, entry)
    await _press(hass, entry)
    with pytest.raises(ServiceValidationError) as err:
        await _press(hass, entry)
    assert err.value.translation_key == "daily_limit_reached"
    assert speed_test.call_count == 2
    assert _state(hass, entry, "speed_test_download") == "245.6"


async def test_limit_and_result_survive_restart(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """The run history and the last result are stored: a reload keeps both."""
    entry = await setup_entry(**CLOUDFLARE, **{CONF_SPEED_TEST_DAILY_LIMIT: 1})
    await _press(hass, entry)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _state(hass, entry, "speed_test_upload") == "11.2"
    with pytest.raises(ServiceValidationError):
        await _press(hass, entry)


async def test_runs_older_than_a_day_do_not_count(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, hass_storage: dict[str, Any]
) -> None:
    """Only runs in the last 24 hours count toward the limit."""
    old = dt_util.utcnow().timestamp() - 25 * 3600
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {"runs": [{"at": old, "automated": False}]},
    }
    entry = await setup_entry(**CLOUDFLARE, **{CONF_SPEED_TEST_DAILY_LIMIT: 1})
    await _press(hass, entry)
    speed_test.assert_called_once()


async def test_removing_entry_deletes_stored_history(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, hass_storage: dict[str, Any]
) -> None:
    """Removing the integration removes its stored speed test data."""
    entry = await setup_entry(**CLOUDFLARE)
    await _press(hass, entry)
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert STORAGE_KEY not in hass_storage


async def test_options_flow_asks_mlab_consent(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Choosing M-Lab asks for consent; declining keeps the form; agreeing saves it with the choice."""
    entry = await setup_entry()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    form = {**entry.options, CONF_SPEED_TEST_BACKEND: "mlab"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], form)
    assert result.get("step_id") == "speed_test"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert (result.get("type"), result.get("step_id")) == (FlowResultType.FORM, "mlab_consent")

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_MLAB_CONSENT: False})
    assert result.get("errors") == {"base": "mlab_consent_required"}

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_MLAB_CONSENT: True})
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert (entry.options[CONF_SPEED_TEST_BACKEND], entry.options[CONF_MLAB_CONSENT]) == ("mlab", True)


async def test_mlab_consent_is_asked_once(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Once given, consent is not asked again on later saves."""
    entry = await setup_entry(**{CONF_SPEED_TEST_BACKEND: "mlab", CONF_MLAB_CONSENT: True})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    form = {key: value for key, value in entry.options.items() if key != CONF_MLAB_CONSENT}
    result = await hass.config_entries.options.async_configure(result["flow_id"], form)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MLAB_CONSENT] is True


async def test_mlab_without_consent_never_runs(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """An entry naming M-Lab without stored consent creates no speed test entities."""
    entry = await setup_entry(**{CONF_SPEED_TEST_BACKEND: "mlab"})
    assert entity_id(hass, "button", entry, "run_speed_test") is None


async def test_turning_speed_tests_off_removes_entities(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """Choosing Off removes the speed test entities (stale-entity cleanup)."""
    entry = await setup_entry(**CLOUDFLARE)
    assert entity_id(hass, "button", entry, "run_speed_test")
    await set_options(hass, entry, {**entry.options, CONF_SPEED_TEST_BACKEND: "none"})
    assert entity_id(hass, "button", entry, "run_speed_test") is None
    assert entity_id(hass, "sensor", entry, "speed_test_download") is None


async def test_diagnostics_include_last_result(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """Diagnostics show the backend's last result."""
    entry = await setup_entry(**CLOUDFLARE)
    await _press(hass, entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["speed_test"]["last_result"]["download_mbps"] == 245.6
    assert DOMAIN in str(diagnostics["speed_test"]["storage_key"])


async def test_setup_flow_asks_mlab_consent(hass: HomeAssistant) -> None:
    """Choosing M-Lab during setup asks for consent before the entry is created."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**DEFAULTS, CONF_SPEED_TEST_BACKEND: "mlab"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result.get("step_id") == "mlab_consent"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MLAB_CONSENT: False})
    assert result.get("errors") == {"base": "mlab_consent_required"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MLAB_CONSENT: True})
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert (result.get("options") or {}).get(CONF_MLAB_CONSENT) is True


async def test_reconfigure_asks_mlab_consent(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Reconfigure to M-Lab asks for consent, then updates the entry."""
    entry = await setup_entry()
    result = await entry.start_reconfigure_flow(hass)
    form = {**entry.options, CONF_SPEED_TEST_BACKEND: "mlab"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**DEFAULTS, **form})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result.get("step_id") == "mlab_consent"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MLAB_CONSENT: True})
    await hass.async_block_till_done()
    assert result.get("reason") == "reconfigure_successful"
    assert entry.options[CONF_SPEED_TEST_BACKEND] == "mlab"


MLAB = {**CLOUDFLARE, CONF_SPEED_TEST_BACKEND: "mlab", CONF_MLAB_CONSENT: True, CONF_SPEED_TEST_DAILY_LIMIT: 40}
WAIT = "custom_components.internet_health_monitor.coordinator.random.uniform"


async def test_mlab_automated_run_waits_a_random_time(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """An automation's press with M-Lab returns at once and the test starts after a random wait (AUP)."""
    entry = await setup_entry(**MLAB)
    with patch(WAIT, return_value=600.0) as wait:
        await _press(hass, entry, by_person=False)
    assert wait.call_args.args == (0, 3600)
    speed_test.assert_not_called()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=601))
    await hass.async_block_till_done()
    speed_test.assert_called_once()
    assert _state(hass, entry, "speed_test_download") == "245.6"


async def test_mlab_automated_runs_capped_at_four(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """M-Lab: a fifth automated run in 24 hours is refused even when Tests per day allows more."""
    entry = await setup_entry(**MLAB)
    with patch(WAIT, return_value=0.0):
        for _ in range(4):
            await _press(hass, entry, by_person=False)
        with pytest.raises(ServiceValidationError) as err:
            await _press(hass, entry, by_person=False)
    assert err.value.translation_key == "mlab_automated_limit"
    await _press(hass, entry)  # a person's press is interactive: allowed up to Tests per day


async def test_mlab_person_press_runs_now(hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock) -> None:
    """A person's press runs M-Lab immediately; only automated runs wait."""
    entry = await setup_entry(**MLAB)
    with patch(WAIT) as wait:
        await _press(hass, entry)
    wait.assert_not_called()
    speed_test.assert_called_once()


async def test_pending_automated_run_is_cancelled_on_unload(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """Unloading the entry cancels a waiting automated run."""
    entry = await setup_entry(**MLAB)
    with patch(WAIT, return_value=600.0):
        await _press(hass, entry, by_person=False)
    assert await hass.config_entries.async_unload(entry.entry_id)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=601))
    await hass.async_block_till_done()
    speed_test.assert_not_called()


# Automatic tests: a random time from 1 to 5 am local, weekly without a budget. HA's test time zone is US/Pacific.
AUTOMATIC = {**CLOUDFLARE, CONF_SPEED_TEST_AUTOMATIC: True}
OFFSET = "custom_components.internet_health_monitor.coordinator.random.randint"


def _local(text: str) -> datetime:
    """A local time in HA's time zone."""
    parsed = dt_util.parse_datetime(text)
    assert parsed is not None
    return parsed.replace(tzinfo=dt_util.get_default_time_zone())


@pytest.mark.parametrize(("now", "last", "days", "offset", "expected"), NEXT_CASES)
async def test_next_automatic_test(
    hass: HomeAssistant, now: str, last: str | None, days: int, offset: int, expected: str
) -> None:
    """The next test is in the first 1 to 5 am window that is still ahead and the spacing allows."""
    last_at = _local(last).timestamp() if last else None
    with patch(OFFSET, return_value=offset) as randint:
        assert next_automatic_test(_local(now), last_at, days) == _local(expected)
    assert randint.call_args.args == (0, 4 * 3600)


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, at: str) -> None:
    """Move to a local time and let anything due run."""
    freezer.move_to(_local(at))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_automatic_tests_weekly_without_a_budget(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """On by default: the first test tonight, then one a week at the random time, and none in between."""
    freezer.move_to(_local("2026-11-19 12:00:00"))
    with patch(OFFSET, return_value=3600):
        entry = await setup_entry(**AUTOMATIC)
        for at, runs in (
            ("2026-11-20 01:59:00", 0),
            ("2026-11-20 02:00:01", 1),
            ("2026-11-21 02:00:01", 1),
            ("2026-11-26 02:00:01", 1),
            ("2026-11-27 02:00:01", 2),
        ):
            await _tick(hass, freezer, at)
            assert speed_test.call_count == runs, at
    assert _state(hass, entry, "speed_test_download") == "245.6"


async def test_budget_sets_the_spacing(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """With a budget, tests run as often as it holds them: 2 GB holds 4 tests of 500 MB, so every 8 days."""
    freezer.move_to(_local("2026-11-19 12:00:00"))
    with patch(OFFSET, return_value=0):
        await setup_entry(**AUTOMATIC, **{CONF_SPEED_TEST_BUDGET: 2, CONF_SPEED_TEST_DATA_LIMIT: 500})
        for at, runs in (("2026-11-20 01:00:01", 1), ("2026-11-27 01:00:01", 1), ("2026-11-28 01:00:01", 2)):
            await _tick(hass, freezer, at)
            assert speed_test.call_count == runs, at


async def test_large_budget_tests_nightly(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """A budget that holds a test every night runs one a night, even when the new random time is later tonight."""
    freezer.move_to(_local("2026-11-19 12:00:00"))
    # 01:00 for the first night; then 04:00, which is still ahead tonight when the first test runs.
    with patch(OFFSET, side_effect=[0, 3 * 3600, 3 * 3600, 3 * 3600]):
        await setup_entry(**AUTOMATIC, **{CONF_SPEED_TEST_BUDGET: 50})
        for at, runs in (("2026-11-20 01:00:01", 1), ("2026-11-20 04:00:01", 1), ("2026-11-21 04:00:01", 2)):
            await _tick(hass, freezer, at)
            assert speed_test.call_count == runs, at


async def test_spacing_survives_restart(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """The last automatic test is stored: after a reload the next is still a week after it."""
    freezer.move_to(_local("2026-11-19 12:00:00"))
    with patch(OFFSET, return_value=0):
        entry = await setup_entry(**AUTOMATIC)
        await _tick(hass, freezer, "2026-11-20 01:00:01")
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        await _tick(hass, freezer, "2026-11-21 01:00:01")
        assert speed_test.call_count == 1
        await _tick(hass, freezer, "2026-11-27 01:00:01")
    assert speed_test.call_count == 2


async def test_automatic_test_counts_as_automated(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """With M-Lab, an automatic test starts at its random time (no extra wait) and counts toward M-Lab's 4."""
    freezer.move_to(_local("2026-11-19 12:00:00"))
    with patch(OFFSET, return_value=0), patch(WAIT, return_value=0.0) as wait:
        entry = await setup_entry(**{**MLAB, CONF_SPEED_TEST_AUTOMATIC: True})
        await _tick(hass, freezer, "2026-11-20 01:00:01")
        speed_test.assert_called_once()
        wait.assert_not_called()
        for _ in range(3):
            await _press(hass, entry, by_person=False)
        with pytest.raises(ServiceValidationError) as err:
            await _press(hass, entry, by_person=False)
    assert err.value.translation_key == "mlab_automated_limit"


async def test_automatic_test_skipped_at_a_limit(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    speed_test: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A test refused by a limit is logged and tried again the next night."""
    freezer.move_to(_local("2026-11-20 00:30:00"))
    with patch(OFFSET, return_value=3600):
        entry = await setup_entry(**AUTOMATIC, **{CONF_SPEED_TEST_DAILY_LIMIT: 1})
        await _press(hass, entry)
        await _tick(hass, freezer, "2026-11-20 02:00:01")
        assert speed_test.call_count == 1
        assert "Automatic speed test skipped" in caplog.text
        await _tick(hass, freezer, "2026-11-21 02:00:01")
    assert speed_test.call_count == 2


async def test_unload_cancels_automatic_test(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """After unload no automatic test runs."""
    freezer.move_to(_local("2026-11-19 12:00:00"))
    entry = await setup_entry(**AUTOMATIC)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await _tick(hass, freezer, "2026-11-21 12:00:00")
    speed_test.assert_not_called()


# 330.4 MB a test, as Core reports it in two parts.
MEASURED = replace(RESULT, downloaded_mb=300.0, uploaded_mb=30.4)


async def test_budget_refuses_a_test_that_may_not_fit(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """A test starts only if its data limit fits what is left of the 30-day budget; old tests drop out."""
    speed_test.return_value = MEASURED
    entry = await setup_entry(**CLOUDFLARE, **{CONF_SPEED_TEST_BUDGET: 1, CONF_SPEED_TEST_DATA_LIMIT: 500})
    await _press(hass, entry)  # 0 + 500 fits 1000 MB
    await _press(hass, entry)  # 330.4 + 500 fits
    with pytest.raises(ServiceValidationError) as err:
        await _press(hass, entry)  # 660.8 + 500 does not
    assert err.value.translation_key == "budget_reached"
    assert err.value.translation_placeholders == {"used": "0.7", "budget": "1", "limit": "500"}
    assert speed_test.call_count == 2

    freezer.tick(timedelta(days=30, seconds=1))
    await _press(hass, entry)
    assert speed_test.call_count == 3


async def test_failed_test_counts_toward_budget(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """The data a failed test moved counts against the budget too."""
    entry = await setup_entry(**CLOUDFLARE, **{CONF_SPEED_TEST_BUDGET: 1, CONF_SPEED_TEST_DATA_LIMIT: 500})
    speed_test.side_effect = SpeedTestError("upload refused", downloaded_mb=450.0, uploaded_mb=100.0)
    with pytest.raises(HomeAssistantError):
        await _press(hass, entry)  # 550 MB moved
    with pytest.raises(ServiceValidationError) as err:
        await _press(hass, entry)
    assert err.value.translation_key == "budget_reached"


async def test_budget_survives_restart(hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock) -> None:
    """The data each run used is stored with it: a reload keeps the budget spent."""
    speed_test.return_value = replace(RESULT, downloaded_mb=600.0, uploaded_mb=0.0)
    entry = await setup_entry(**CLOUDFLARE, **{CONF_SPEED_TEST_BUDGET: 1, CONF_SPEED_TEST_DATA_LIMIT: 500})
    await _press(hass, entry)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await _press(hass, entry)


async def test_unload_cancels_every_waiting_mlab_run(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """Waits are random, so runs finish waiting out of order; unload still cancels the one left."""
    entry = await setup_entry(**MLAB)
    with patch(WAIT, side_effect=[500.0, 100.0]):
        await _press(hass, entry, by_person=False)  # A waits 500 s
        await _press(hass, entry, by_person=False)  # B waits 100 s
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=101))
    await hass.async_block_till_done()
    assert speed_test.call_count == 1  # B ran
    assert await hass.config_entries.async_unload(entry.entry_id)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=501))
    await hass.async_block_till_done()
    assert speed_test.call_count == 1  # A never runs after unload


async def test_speed_test_in_flight_at_unload(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """A test that finishes after the entry unloaded neither crashes nor counts its data again."""
    entry = await setup_entry(**CLOUDFLARE)
    release = asyncio.Event()

    async def slow_test(*_: Any, **__: Any) -> SpeedTestResult:
        await release.wait()
        return RESULT

    speed_test.side_effect = slow_test
    usage = entry.runtime_data.coordinator.usage
    press = hass.async_create_task(_press(hass, entry))
    await asyncio.sleep(0.01)
    assert await hass.config_entries.async_unload(entry.entry_id)
    release.set()
    await press
    await hass.async_block_till_done()
    assert usage.totals.downloaded_mb == 0.0


async def test_waiting_run_uses_the_limit_it_reserved(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock
) -> None:
    """An automated M-Lab run waits; a test in between changes the automatic limit, but it keeps the one it reserved."""
    entry = await setup_entry(**MLAB, **{CONF_SPEED_TEST_DATA_LIMIT: 0})
    with patch(WAIT, return_value=100.0):
        await _press(hass, entry, by_person=False)  # reserves 500 MB, split evenly: no result yet
    await _press(hass, entry)  # a person's test now: its result sizes the next limit at 390 / 50
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=101))
    await hass.async_block_till_done()
    assert [c.args[2] for c in speed_test.call_args_list] == [DataLimit(250, 250), DataLimit(250, 250)]
