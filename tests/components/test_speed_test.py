"""Speed tests in HA: options and M-Lab consent, sensors, the button, limits and persistence."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
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
    CONF_SPEED_TEST_BACKEND,
    CONF_SPEED_TEST_DAILY_LIMIT,
    CONF_SPEED_TEST_DATA_LIMIT,
    DOMAIN,
)
from custom_components.internet_health_monitor.coordinator import STORAGE_KEY
from custom_components.internet_health_monitor.diagnostics import async_get_config_entry_diagnostics
from solentlabs.internet_health_monitor_core.speed_test import SpeedTestError, SpeedTestResult

from .conftest import SetupEntry, entity_id

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
)
CLOUDFLARE = {CONF_SPEED_TEST_BACKEND: "cloudflare"}
SPEED_SENSORS = [
    "speed_test_download",
    "speed_test_upload",
    "speed_test_idle_latency",
    "speed_test_download_latency",
    "speed_test_upload_latency",
    "speed_test_data_used",
]


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
    """Setup and time passing never start a test; sensors read unknown until one runs."""
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
# └──────────────────────────────┴──────────┘
# fmt: off
STATE_CASES: list[tuple[str, str]] = [
    ("speed_test_download",         "245.6"),
    ("speed_test_upload",           "11.2"),
    ("speed_test_idle_latency",     "12.0"),
    ("speed_test_download_latency", "48.5"),
    ("speed_test_upload_latency",   "310.0"),
    ("speed_test_data_used",        "330.4"),
]
# fmt: on


@pytest.mark.parametrize("key,expected", STATE_CASES)
async def test_press_runs_and_fills_sensors(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test: AsyncMock, key: str, expected: str
) -> None:
    """A press runs one test with the chosen backend and data limit; each sensor shows its field."""
    entry = await setup_entry(**CLOUDFLARE, **{CONF_SPEED_TEST_DATA_LIMIT: 500})
    await _press(hass, entry)
    assert speed_test.call_args.args[0] == "cloudflare"
    assert speed_test.call_args.kwargs["data_limit_mb"] == 500
    assert _state(hass, entry, key) == expected
    attrs = hass.states.get(entity_id(hass, "sensor", entry, key) or "")
    assert attrs is not None
    assert (attrs.attributes["backend"], attrs.attributes["server"]) == ("cloudflare", "speed.cloudflare.com")
    assert "tested_at" in attrs.attributes


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
    assert (result["type"], result["step_id"]) == (FlowResultType.FORM, "mlab_consent")

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_MLAB_CONSENT: False})
    assert result["errors"] == {"base": "mlab_consent_required"}

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_MLAB_CONSENT: True})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (entry.options[CONF_SPEED_TEST_BACKEND], entry.options[CONF_MLAB_CONSENT]) == ("mlab", True)


async def test_mlab_consent_is_asked_once(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Once given, consent is not asked again on later saves."""
    entry = await setup_entry(**{CONF_SPEED_TEST_BACKEND: "mlab", CONF_MLAB_CONSENT: True})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    form = {key: value for key, value in entry.options.items() if key != CONF_MLAB_CONSENT}
    result = await hass.config_entries.options.async_configure(result["flow_id"], form)
    assert result["type"] is FlowResultType.CREATE_ENTRY
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
    hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_SPEED_TEST_BACKEND: "none"})
    await hass.async_block_till_done()
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
    assert result["step_id"] == "mlab_consent"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MLAB_CONSENT: False})
    assert result["errors"] == {"base": "mlab_consent_required"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MLAB_CONSENT: True})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_MLAB_CONSENT] is True


async def test_reconfigure_asks_mlab_consent(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Reconfigure to M-Lab asks for consent, then updates the entry."""
    entry = await setup_entry()
    result = await entry.start_reconfigure_flow(hass)
    form = {**entry.options, CONF_SPEED_TEST_BACKEND: "mlab"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**DEFAULTS, **form})
    assert result["step_id"] == "mlab_consent"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MLAB_CONSENT: True})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.options[CONF_SPEED_TEST_BACKEND] == "mlab"


MLAB = {CONF_SPEED_TEST_BACKEND: "mlab", CONF_MLAB_CONSENT: True, CONF_SPEED_TEST_DAILY_LIMIT: 40}
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
