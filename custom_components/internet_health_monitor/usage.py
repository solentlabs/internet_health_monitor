"""Usage totals: everything IHM has sent since install, kept in HA storage (README.md § Usage Totals)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from solentlabs.internet_health_monitor_core.network_diagnostics import ProbeCounts
from solentlabs.internet_health_monitor_core.timing import USAGE_SAVE_DELAY_S

from .const import DOMAIN

STORAGE_KEY = f"{DOMAIN}.usage"
STORAGE_VERSION = 1


@dataclass
class UsageTotals:
    """Running totals since install."""

    pings: int = 0
    traceroutes: int = 0
    dns_queries: int = 0
    speed_tests: int = 0  # accepted runs, failed ones included
    downloaded_mb: float = 0.0  # every speed test, failed ones included
    uploaded_mb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Plain data for storage and diagnostics."""
        return asdict(self)


class UsageTracker:
    """Adds Core's per-instance counts and each speed test to the stored totals."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Totals load from storage before the first poll."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._base = UsageTotals()  # probe totals stored before this Core instance started
        self.totals = UsageTotals()

    async def async_load(self) -> None:
        """Start from the stored totals."""
        stored = await self._store.async_load() or {}
        known = {f.name for f in fields(UsageTotals)}
        self._base = UsageTotals(**{k: v for k, v in stored.items() if k in known})
        self.totals = UsageTotals(**self._base.to_dict())

    def add_probes(self, counts: ProbeCounts) -> None:
        """Totals = stored base + what this Core instance has sent."""
        self.totals.pings = self._base.pings + counts.pings
        self.totals.traceroutes = self._base.traceroutes + counts.traceroutes
        self.totals.dns_queries = self._base.dns_queries + counts.dns_queries
        self._store.async_delay_save(self.totals.to_dict, USAGE_SAVE_DELAY_S)

    def add_speed_test_run(self) -> None:
        """Count one accepted speed test."""
        self.totals.speed_tests += 1
        self._store.async_delay_save(self.totals.to_dict, USAGE_SAVE_DELAY_S)

    def add_speed_test_data(self, downloaded_mb: float, uploaded_mb: float) -> None:
        """Add the data a test moved, whether it completed or failed partway."""
        self.totals.downloaded_mb = round(self.totals.downloaded_mb + downloaded_mb, 1)
        self.totals.uploaded_mb = round(self.totals.uploaded_mb + uploaded_mb, 1)
        self._store.async_delay_save(self.totals.to_dict, USAGE_SAVE_DELAY_S)

    async def async_save(self) -> None:
        """Write now (unload), replacing any pending delayed write."""
        await self._store.async_save(self.totals.to_dict())
