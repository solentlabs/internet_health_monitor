"""Coordinator and runtime data for Internet Health Monitor."""

from __future__ import annotations

import logging
import random
from collections.abc import Coroutine
from dataclasses import asdict, dataclass, field
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

from solentlabs.internet_health_monitor_core.data_plan import automatic_limit, every_days
from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics, NetworkDiagnosticsResult
from solentlabs.internet_health_monitor_core.reachability import Reachability
from solentlabs.internet_health_monitor_core.speed_test import (
    BackendName,
    DataLimit,
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
    SPEED_TEST_DATA_LIMIT_MB_AUTO,
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
        self._unloaded = False  # a check or poll still running at unload must not schedule another
        entry.async_on_unload(self._cancel_checks)

    def _cancel_checks(self) -> None:
        """Cancel quick checks still waiting (the entry is unloading)."""
        self._unloaded = True
        for cancel in self._pending.values():
            cancel()
        self._pending.clear()

    def _observe(self, target: ReachabilityTarget, ok: bool) -> None:
        """Feed one result to *target*; schedule the quick check it asks for, or cancel one no longer needed."""
        if self._unloaded:
            return
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
        ok = await check()
        if self._unloaded:
            return  # unloaded while the check ran
        self._observe(target, ok)
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


def next_automatic_test(now: datetime, last_at: float | None, days: int) -> datetime:
    """A random time in the overnight window (timing.SPEED_TEST_AUTO_*), local time.

    The night is the first still ahead that is at least *days* after the last automatic test's.
    """
    local = dt_util.as_local(now)
    night = dt_util.start_of_local_day(local)
    if last_at is not None:
        last_night = dt_util.start_of_local_day(dt_util.as_local(dt_util.utc_from_timestamp(last_at)))
        night = max(night, last_night + timedelta(days=days))
    offset = random.randint(0, SPEED_TEST_AUTO_WINDOW_S)  # noqa: S311  # spreading load, not security
    when = night + timedelta(hours=SPEED_TEST_AUTO_START_HOUR, seconds=offset)
    return when if when > local else when + timedelta(days=1)


class SpeedTestCoordinator(DataUpdateCoordinator[SpeedTestResult | None]):
    """Runs a speed test when asked (button or automation) and, if chosen, automatically (ADR-003)."""

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
        """Hold the user's backend and limits (data limit 0: automatic); history and last result load from storage."""
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
        self._pending: dict[int, CALLBACK_TYPE] = {}  # automated M-Lab runs waiting, by id(run)
        self._limits: dict[int, DataLimit] = {}  # each accepted run's limit, as reserved, by id(run)
        self._limit = DataLimit.even(0)  # the running test's limit
        self._automatic: CALLBACK_TYPE | None = None
        self._last_automatic: float | None = None  # when the last automatic test started
        self._unloaded = False  # a test still running at unload must not touch the entry
        entry.async_on_unload(self._cancel_pending)

    async def async_load(self) -> None:
        """Restore run times (for the limits), the last automatic test and result; schedule the next if chosen."""
        stored = await self._store.async_load() or {}
        self._runs = list(stored.get("runs", []))
        self._last_automatic = stored.get("last_automatic")
        if last := stored.get("last"):
            self.data = SpeedTestResult(**last)
        if self.automatic:
            self._schedule_automatic()

    def data_limit(self) -> DataLimit:
        """The next test's limit: the user's, split evenly, or automatic from the last result (data_plan.py)."""
        if self.data_limit_mb == SPEED_TEST_DATA_LIMIT_MB_AUTO:
            return automatic_limit(self.data, self.budget_gb)
        return DataLimit.even(self.data_limit_mb)

    def every_days(self) -> int | None:
        """Days between automatic tests at the next test's limit; None if no test fits the budget."""
        return every_days(self.data_limit(), self.budget_gb)

    def _schedule_automatic(self, *, after_tonight: bool = False) -> None:
        """Schedule the next automatic test; after a refusal, from the end of tonight's window (one a night)."""
        days = self.every_days()
        if days is None:  # the form refuses such a limit; an automatic one always fits
            return
        now = dt_util.utcnow()
        if after_tonight:
            start = dt_util.start_of_local_day(dt_util.as_local(now))
            now = start + timedelta(hours=SPEED_TEST_AUTO_START_HOUR, seconds=SPEED_TEST_AUTO_WINDOW_S)
        when = next_automatic_test(now, self._last_automatic, days)
        job: QuickCheckJob = HassJob(self._async_run_automatic, cancel_on_shutdown=True)
        self._automatic = async_track_point_in_utc_time(self.hass, job, dt_util.as_utc(when))

    async def _async_run_automatic(self, _now: datetime) -> None:
        """Run an automatic test unless a limit refuses it; a refusal is logged and tried the next night."""
        self._automatic = None
        try:
            run = self._accept(dt_util.utcnow().timestamp(), automated=True)
        except ServiceValidationError as err:
            _LOGGER.info("Automatic speed test skipped: %s", err)
            self._schedule_automatic(after_tonight=True)
            return
        self._last_automatic = run["at"]
        await self._async_test(run)
        if not self._unloaded:
            self._schedule_automatic()  # from this test, at the spacing its result now gives

    async def _async_save(self) -> None:
        """Store run times, the last automatic test and the last result."""
        await self._store.async_save(
            {
                "runs": self._runs,
                "last_automatic": self._last_automatic,
                "last": asdict(self.data) if self.data else None,
            }
        )

    def _cancel_pending(self) -> None:
        """Cancel the automatic test and automated runs still waiting (the entry is unloading)."""
        self._unloaded = True
        for cancel in self._pending.values():
            cancel()
        self._pending.clear()
        if self._automatic:
            self._automatic()
            self._automatic = None

    def _accept(self, now: float, *, automated: bool) -> dict[str, Any]:
        """Check the limits, then record the run; it counts from here, failed or not."""
        limit = self.data_limit()
        self._check_limits(now, automated, limit.total_mb)
        run = {"at": now, "automated": automated, "mb": float(limit.total_mb)}
        self._limits[id(run)] = limit  # a run that waits still tests within what it reserved
        self._runs.append(run)
        self.usage.add_speed_test_run()
        return run

    def _check_limits(self, now: float, automated: bool, limit_mb: int) -> None:
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
        if self.budget_gb and used_mb + limit_mb > self.budget_gb * 1000:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="budget_reached",
                translation_placeholders={
                    "used": f"{used_mb / 1000:.1f}",
                    "budget": str(self.budget_gb),
                    "limit": str(limit_mb),
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
            self._pending[id(run)] = async_call_later(self.hass, delay, job)
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
        self._limit = self._limits.pop(id(run))
        await self.async_refresh()
        if self._unloaded:
            return  # unloaded mid-test: HA dropped the entry's runtime data
        if self.last_update_success and self.data:
            self.usage.add_speed_test_data(self.data.downloaded_mb, self.data.uploaded_mb)
            self._last_mb = self.data.downloaded_mb + self.data.uploaded_mb
        run["mb"] = round(self._last_mb, 1)
        await self._async_save()
        # Usage sensors belong to the poll coordinator; show the new totals now.
        self.config_entry.runtime_data.coordinator.async_update_listeners()

    async def _async_run_waiting(self, run: dict[str, Any], _now: datetime) -> None:
        """Start an automated run whose random wait is over; a failure shows on the sensors."""
        self._pending.pop(id(run), None)  # waits are random: runs finish waiting in any order
        await self._async_test(run)

    @override
    async def _async_update_data(self) -> SpeedTestResult | None:
        """Run the test with HA's shared web session (inject-websession)."""
        try:
            return await run_speed_test(self.backend, async_get_clientsession(self.hass), self._limit)
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
