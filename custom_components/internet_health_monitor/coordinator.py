"""Coordinator and runtime data for Internet Health Monitor."""

from __future__ import annotations

import logging
import random
from collections.abc import Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from typing import Any, Literal, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics, NetworkDiagnosticsResult
from solentlabs.internet_health_monitor_core.reachability import Reachability
from solentlabs.internet_health_monitor_core.speed_test import (
    BackendName,
    SpeedTestError,
    SpeedTestResult,
    run_speed_test,
)
from solentlabs.internet_health_monitor_core.timing import (
    POLL_INTERVAL_S,
    SPEED_TEST_AUTO_START_HOUR,
    SPEED_TEST_AUTO_WINDOW_S,
    SPEED_TEST_BUDGET_WINDOW_S,
    SPEED_TEST_DAILY_WINDOW_S,
    SPEED_TEST_MLAB_AUTOMATED_DAILY,
    SPEED_TEST_MLAB_AUTOMATED_WAIT_MAX_S,
)

from .const import DOMAIN
from .usage import UsageTracker

_LOGGER = logging.getLogger(__name__)

# Fixed poll interval from Core (ADR-007; HA quality scale appropriate-polling).
# Users who want another interval disable polling and call
# homeassistant.update_entity from an automation (README.md § Polling).
SCAN_INTERVAL = timedelta(seconds=POLL_INTERVAL_S)

ReachabilityTarget = Literal["gateway", "internet"]
# What async_call_later accepts; HassJob is invariant in its return type.
type QuickCheckJob = HassJob[[datetime], Coroutine[Any, Any, None] | None]


@dataclass
class InternetHealthRuntimeData:
    """What one config entry holds while loaded."""

    coordinator: InternetHealthCoordinator
    diagnostics: NetworkDiagnostics
    enable_gateway: bool
    enable_dns: bool
    # Usage total sensors exist only when chosen; the totals are kept either way.
    usage_totals: bool
    # Measurement sensors carry state_class only when chosen: HA never purges their statistics (ADR-013).
    long_term_statistics: bool
    # HA's own installation type, read once at setup (sensor.py INSTALL_TYPES).
    installation_type: str
    # Present only when the user chose a speed test backend (and, for M-Lab, consented).
    speed_test: SpeedTestCoordinator | None = None
    # Unique ids of the entities this setup created; setup removes any others (README.md § Configuration).
    unique_ids: set[str] = field(default_factory=set)


type InternetHealthConfigEntry = ConfigEntry[InternetHealthRuntimeData]


class InternetHealthCoordinator(DataUpdateCoordinator[NetworkDiagnosticsResult]):
    """Runs one diagnostics poll per interval."""

    config_entry: InternetHealthConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: InternetHealthConfigEntry,
        diagnostics: NetworkDiagnostics,
        usage: UsageTracker,
        targets: tuple[ReachabilityTarget, ...] = ("gateway", "internet"),
    ) -> None:
        """Poll every SCAN_INTERVAL, adding what each poll sends to *usage*; track reachability of *targets*."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.diagnostics = diagnostics
        self.usage = usage
        # Confirm before off, re-check fast while off (ADR-012); quick checks run only then.
        self.reachability: dict[ReachabilityTarget, Reachability] = {t: Reachability() for t in targets}
        self._pending: dict[ReachabilityTarget, CALLBACK_TYPE] = {}
        entry.async_on_unload(self._cancel_checks)

    def _cancel_checks(self) -> None:
        """Cancel quick checks still waiting (the entry is unloading)."""
        for cancel in self._pending.values():
            cancel()
        self._pending.clear()

    def _observe(self, target: ReachabilityTarget, ok: bool) -> None:
        """Feed one result to *target*; schedule the quick check it asks for, or cancel one no longer needed."""
        delay = self.reachability[target].observe(ok)
        if delay is None:
            if cancel := self._pending.pop(target, None):
                cancel()
        elif target not in self._pending:
            job: QuickCheckJob = HassJob(partial(self._async_quick_check, target), cancel_on_shutdown=True)
            self._pending[target] = async_call_later(self.hass, delay, job)

    async def _async_quick_check(self, target: ReachabilityTarget, _now: datetime) -> None:
        """One gateway ping or one DNS query, then show the result."""
        self._pending.pop(target, None)
        check = self.diagnostics.check_gateway if target == "gateway" else self.diagnostics.check_internet
        self._observe(target, await check())
        self.usage.add_probes(self.diagnostics.counts)
        self.async_update_listeners()

    @override
    async def _async_update_data(self) -> NetworkDiagnosticsResult:
        """Run one poll; a failure marks entities unavailable until the next success."""
        try:
            result = await self.diagnostics.run_diagnostics()
        except Exception as err:  # a failed poll still sent its probes; finally counts them
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        finally:
            self.usage.add_probes(self.diagnostics.counts)
        observed = {"gateway": result.gateway_reachable, "internet": result.dns_success}
        for target in self.reachability:
            self._observe(target, observed[target])
        return result


STORAGE_KEY = f"{DOMAIN}.speed_test"
STORAGE_VERSION = 1  # __init__.async_remove_entry opens the same store to delete it


def next_nightly_test(now: datetime) -> datetime:
    """A random time in the next overnight window (timing.SPEED_TEST_AUTO_*), local time."""
    local = dt_util.as_local(now)
    offset = random.randint(0, SPEED_TEST_AUTO_WINDOW_S)  # noqa: S311  # spreading load, not security
    when = dt_util.start_of_local_day(local) + timedelta(hours=SPEED_TEST_AUTO_START_HOUR, seconds=offset)
    return when if when > local else when + timedelta(days=1)


class SpeedTestCoordinator(DataUpdateCoordinator[SpeedTestResult | None]):
    """Runs a speed test when asked (button or automation) and, if chosen, once a night (ADR-003)."""

    config_entry: InternetHealthConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: InternetHealthConfigEntry,
        backend: BackendName,
        data_limit_mb: int,
        daily_limit: int,
        usage: UsageTracker,
        *,
        automatic: bool = False,
        budget_gb: int = 0,
    ) -> None:
        """Hold the user's backend and limits; the run history and last result load from storage."""
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} speed test", update_interval=None)
        self.backend: BackendName = backend
        self.data_limit_mb = data_limit_mb
        self.daily_limit = daily_limit
        self.usage = usage
        self.automatic = automatic
        self.budget_gb = budget_gb
        self.data = None
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        # {"at": epoch seconds, "automated": no person started it, "mb": data used, the limit until it ends}
        self._runs: list[dict[str, Any]] = []
        self._failure = ""  # Core's reason for the last failed test
        self._last_mb = 0.0  # data the last test moved, completed or failed
        self._pending: list[CALLBACK_TYPE] = []  # automated M-Lab runs waiting to start
        self._nightly: CALLBACK_TYPE | None = None
        entry.async_on_unload(self._cancel_pending)

    async def async_load(self) -> None:
        """Restore run times (for the limits) and the last result, then schedule the nightly test if chosen."""
        stored = await self._store.async_load() or {}
        self._runs = list(stored.get("runs", []))
        if last := stored.get("last"):
            self.data = SpeedTestResult(**last)
        if self.automatic:
            self._schedule_nightly()

    def _schedule_nightly(self) -> None:
        """Schedule the next nightly test."""
        when = next_nightly_test(dt_util.utcnow())
        job: QuickCheckJob = HassJob(self._async_run_nightly, cancel_on_shutdown=True)
        self._nightly = async_track_point_in_utc_time(self.hass, job, dt_util.as_utc(when))

    async def _async_run_nightly(self, _now: datetime) -> None:
        """Run the nightly test unless a limit refuses it; a refusal is logged, a failure shows on the sensors."""
        self._schedule_nightly()
        try:
            run = self._accept(dt_util.utcnow().timestamp(), automated=True)
        except ServiceValidationError as err:
            _LOGGER.info("Nightly speed test skipped: %s", err)
            return
        await self._async_test(run)

    async def _async_save(self) -> None:
        """Store run times and the last result."""
        await self._store.async_save({"runs": self._runs, "last": self.data.to_dict() if self.data else None})

    def _cancel_pending(self) -> None:
        """Cancel the nightly test and automated runs still waiting (the entry is unloading)."""
        for cancel in self._pending:
            cancel()
        self._pending.clear()
        if self._nightly:
            self._nightly()
            self._nightly = None

    def _accept(self, now: float, *, automated: bool) -> dict[str, Any]:
        """Check the limits, then record the run; it counts from here, failed or not."""
        self._check_limits(now, automated)
        run = {"at": now, "automated": automated, "mb": float(self.data_limit_mb)}
        self._runs.append(run)
        self.usage.add_speed_test_run()
        return run

    def _check_limits(self, now: float, automated: bool) -> None:
        """Refuse a run past Tests per day, the data budget, or, for M-Lab, its automated limit (R9)."""
        self._runs = [run for run in self._runs if now - run["at"] < SPEED_TEST_BUDGET_WINDOW_S]
        today = [run for run in self._runs if now - run["at"] < SPEED_TEST_DAILY_WINDOW_S]
        if len(today) >= self.daily_limit:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="daily_limit_reached",
                translation_placeholders={"limit": str(self.daily_limit)},
            )
        # A run may use up to the data limit, so it starts only if that still fits the budget.
        used_mb = sum(run.get("mb", 0.0) for run in self._runs)
        if self.budget_gb and used_mb + self.data_limit_mb > self.budget_gb * 1000:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="budget_reached",
                translation_placeholders={
                    "used": f"{used_mb / 1000:.1f}",
                    "budget": str(self.budget_gb),
                    "limit": str(self.data_limit_mb),
                },
            )
        automated_runs = sum(1 for run in today if run["automated"])
        if self.backend == "mlab" and automated and automated_runs >= SPEED_TEST_MLAB_AUTOMATED_DAILY:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="mlab_automated_limit",
                translation_placeholders={"limit": str(SPEED_TEST_MLAB_AUTOMATED_DAILY)},
            )

    async def async_run(self, *, automated: bool) -> None:
        """Run one test; *automated* means no person started it (an automation or script).

        M-Lab asks automated clients to randomize test times (R9): such a run is
        scheduled after a random wait and this returns at once. Every other run
        happens now and raises a translated error if it fails.
        """
        # A run counts when accepted: a failed or waiting run still uses the allowance.
        run = self._accept(dt_util.utcnow().timestamp(), automated=automated)
        if self.backend == "mlab" and automated:
            await self._async_save()
            delay = random.uniform(
                0, SPEED_TEST_MLAB_AUTOMATED_WAIT_MAX_S
            )  # noqa: S311  # spreading load, not security
            job: QuickCheckJob = HassJob(partial(self._async_run_waiting, run), cancel_on_shutdown=True)
            self._pending.append(async_call_later(self.hass, delay, job))
            return
        await self._async_test(run)
        if not self.last_update_success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="speed_test_failed",
                translation_placeholders={"error": self._failure},
            )

    async def _async_test(self, run: dict[str, Any]) -> None:
        """Run the test, store the history and result, and add its data to the usage totals and the budget."""
        self._last_mb = 0.0
        await self.async_refresh()
        if self.last_update_success and self.data:
            self.usage.add_speed_test_data(self.data.downloaded_mb, self.data.uploaded_mb)
            self._last_mb = self.data.downloaded_mb + self.data.uploaded_mb
        run["mb"] = round(self._last_mb, 1)
        await self._async_save()
        # Usage sensors belong to the poll coordinator; show the new totals now.
        self.config_entry.runtime_data.coordinator.async_update_listeners()

    async def _async_run_waiting(self, run: dict[str, Any], _now: datetime) -> None:
        """Start an automated run whose random wait is over; a failure shows on the sensors."""
        self._pending = self._pending[1:]
        await self._async_test(run)

    @override
    async def _async_update_data(self) -> SpeedTestResult | None:
        """Run the test with HA's shared web session (inject-websession)."""
        try:
            return await run_speed_test(
                self.backend, async_get_clientsession(self.hass), data_limit_mb=self.data_limit_mb
            )
        except SpeedTestError as err:
            # The data a failed test moved still counts against the user's cap.
            self.usage.add_speed_test_data(err.downloaded_mb, err.uploaded_mb)
            self._last_mb = err.downloaded_mb + err.uploaded_mb
            self._failure = str(err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="speed_test_failed",
                translation_placeholders={"error": self._failure},
            ) from err
