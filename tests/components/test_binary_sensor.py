"""Tests for the reachability binary sensors."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.internet_health_monitor.const import CONF_ENABLE_DNS_MONITORING
from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics

from .conftest import SetupEntry, entity_id, make_result

# First poll -> (gateway reachable, internet reachable). A failure is not shown until
# quick checks confirm it (ADR-012), so a first-poll failure reads unknown.
# fmt: off
REACHABILITY_CASES = [
    ("both answer",     {},                                                  (STATE_ON, STATE_ON)),
    ("gateway silent",  {"gateway_reachable": False},                        (STATE_UNKNOWN, STATE_ON)),
    ("dns failed",      {"dns_success": False, "dns_latency_ms": None},      (STATE_ON, STATE_UNKNOWN)),
]
# fmt: on


def _states(hass: HomeAssistant, entry: MockConfigEntry) -> tuple[str, str]:
    """(gateway reachable, internet reachable) states."""
    return tuple(  # type: ignore[return-value]
        hass.states.get(entity_id(hass, "binary_sensor", entry, key) or "").state  # type: ignore[union-attr]
        for key in ("gateway_reachable", "internet_reachable")
    )


@pytest.mark.parametrize(
    ("description", "overrides", "expected"), REACHABILITY_CASES, ids=[c[0] for c in REACHABILITY_CASES]
)
async def test_reachability(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    poll: AsyncMock,
    description: str,
    overrides: dict[str, Any],
    expected: tuple[str, str],
) -> None:
    """Each sensor is on when its target answered; an unconfirmed failure is not yet off."""
    poll.return_value = make_result(**overrides)
    entry = await setup_entry()
    assert _states(hass, entry) == expected


async def _advance(hass: HomeAssistant, seconds: float) -> None:
    """Move time forward and let scheduled checks run."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_outage_confirmed_then_recovery_is_fast(
    hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """A failed poll triggers quick checks; three failures turn it off; while off, a check every 10 s sees recovery."""
    entry = await setup_entry()
    check = AsyncMock(return_value=False)
    with patch.object(NetworkDiagnostics, "check_gateway", check):
        poll.return_value = make_result(gateway_reachable=False)
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()
        assert _states(hass, entry)[0] == STATE_ON  # not yet confirmed
        for _ in range(2):
            freezer.tick(5)
            await _advance(hass, 0)
        assert _states(hass, entry)[0] == STATE_OFF
        assert check.call_count == 2

        check.return_value = True
        freezer.tick(10)
        await _advance(hass, 0)
        assert _states(hass, entry)[0] == STATE_ON
        assert check.call_count == 3
        poll.return_value = make_result()  # the next regular poll sees the gateway too
        freezer.tick(60)
        await _advance(hass, 0)
        assert check.call_count == 3  # healthy again: no more quick checks


async def test_one_lost_packet_never_shows(
    hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """A single failed DNS query is re-checked once and never turns Internet reachable off."""
    entry = await setup_entry()
    check = AsyncMock(return_value=True)
    with patch.object(NetworkDiagnostics, "check_internet", check):
        poll.return_value = make_result(dns_success=False, dns_latency_ms=None)
        await entry.runtime_data.coordinator.async_refresh()
        freezer.tick(5)
        await _advance(hass, 0)
        freezer.tick(30)
        await _advance(hass, 0)
    assert _states(hass, entry)[1] == STATE_ON
    check.assert_called_once()


async def test_healthy_runs_no_quick_checks(
    hass: HomeAssistant, setup_entry: SetupEntry, freezer: FrozenDateTimeFactory
) -> None:
    """While everything answers, nothing runs between polls."""
    entry = await setup_entry()
    gateway, internet = AsyncMock(), AsyncMock()
    with (
        patch.object(NetworkDiagnostics, "check_gateway", gateway),
        patch.object(NetworkDiagnostics, "check_internet", internet),
    ):
        freezer.tick(300)
        await _advance(hass, 0)
    gateway.assert_not_called()
    internet.assert_not_called()
    assert entry.runtime_data.coordinator.reachability["gateway"].state == "up"


async def test_unload_cancels_pending_checks(
    hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """A quick check waiting when the entry unloads never runs."""
    entry = await setup_entry()
    check = AsyncMock(return_value=False)
    with patch.object(NetworkDiagnostics, "check_gateway", check):
        poll.return_value = make_result(gateway_reachable=False)
        await entry.runtime_data.coordinator.async_refresh()
        assert await hass.config_entries.async_unload(entry.entry_id)
        freezer.tick(30)
        await _advance(hass, 0)
    check.assert_not_called()


async def test_dns_off_removes_internet_sensor(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """With DNS monitoring off there is no internet reachability sensor."""
    entry = await setup_entry(**{CONF_ENABLE_DNS_MONITORING: False})
    assert entity_id(hass, "binary_sensor", entry, "internet_reachable") is None
    assert entity_id(hass, "binary_sensor", entry, "gateway_reachable") is not None


async def test_failed_poll_makes_entities_unavailable(
    hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock
) -> None:
    """A failed poll is unavailable, not 'off': a broken monitor is not an outage."""
    entry = await setup_entry()
    poll.side_effect = OSError("boom")
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id(hass, "binary_sensor", entry, "gateway_reachable") or "")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_successful_poll_cancels_waiting_check(
    hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """A poll that answers while a quick check is waiting cancels it: no stray checks after recovery."""
    entry = await setup_entry()
    check = AsyncMock(return_value=False)
    with patch.object(NetworkDiagnostics, "check_gateway", check):
        poll.return_value = make_result(gateway_reachable=False)
        await entry.runtime_data.coordinator.async_refresh()
        poll.return_value = make_result()
        await entry.runtime_data.coordinator.async_refresh()
        freezer.tick(30)
        await _advance(hass, 0)
    check.assert_not_called()
    assert _states(hass, entry)[0] == STATE_ON


async def test_check_in_flight_at_unload_schedules_nothing(
    hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """A quick check still running when the entry unloads does not start the next one."""
    entry = await setup_entry()
    release = asyncio.Event()

    async def slow_check() -> bool:
        await release.wait()
        return False

    check = AsyncMock(side_effect=slow_check)
    with patch.object(NetworkDiagnostics, "check_gateway", check):
        poll.return_value = make_result(gateway_reachable=False)
        await entry.runtime_data.coordinator.async_refresh()
        freezer.tick(5)
        async_fire_time_changed(hass)
        await asyncio.sleep(0)  # the check starts and waits
        assert await hass.config_entries.async_unload(entry.entry_id)
        release.set()
        await hass.async_block_till_done()
        for _ in range(3):
            freezer.tick(10)
            await _advance(hass, 0)
    assert check.call_count == 1


async def test_poll_in_flight_at_unload_schedules_nothing(
    hass: HomeAssistant, setup_entry: SetupEntry, poll: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """A poll that fails after the entry unloaded does not start quick checks."""
    entry = await setup_entry()
    release = asyncio.Event()

    async def slow_poll() -> Any:
        await release.wait()
        return make_result(gateway_reachable=False)

    check = AsyncMock(return_value=False)
    with patch.object(NetworkDiagnostics, "check_gateway", check):
        poll.side_effect = slow_poll
        refresh = hass.async_create_task(entry.runtime_data.coordinator.async_refresh())
        await asyncio.sleep(0)
        coordinator = entry.runtime_data.coordinator
        assert await hass.config_entries.async_unload(entry.entry_id)
        release.set()
        await refresh
        freezer.tick(30)
        await _advance(hass, 0)
    check.assert_not_called()
    assert coordinator._pending == {}  # noqa: SLF001
