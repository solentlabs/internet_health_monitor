"""How much data a speed test may use, and how often automatic tests fit a budget (data_plan.py)."""

from __future__ import annotations

import pytest

from solentlabs.internet_health_monitor_core.data_plan import automatic_limit, every_days, full_test_mb, most_tests
from solentlabs.internet_health_monitor_core.speed_test import DataLimit, SpeedTestResult


def _result(download_mbps: float, upload_mbps: float) -> SpeedTestResult:
    """A completed test at these speeds."""
    return SpeedTestResult("cloudflare", "s", download_mbps, upload_mbps, 10.0, 20.0, 30.0, 1.0, 0.0)


# Last test's speeds and the budget -> each direction's automatic limit. Each direction gets
# 10 s at the last speed plus 25%, in whole 10 MB, at least 50 and at most 5000. A budget too
# small for both keeps the smaller direction's full share where it can.
# ┌──────────────────────┬───────────┬────────────────┬───────────────────────────────┐
# │ last test (Mbit/s)   │ budget GB │ limit down/up  │ why                           │
# ├──────────────────────┼───────────┼────────────────┼───────────────────────────────┤
# │ none                 │ 0         │ 250 / 250      │ first test: 500 MB calibrates │
# │ 100 / 10             │ 0         │ 160 / 50       │ upload at the 50 MB floor     │
# │ 300 / 20             │ 0         │ 470 / 50       │                               │
# │ 1000 / 40            │ 0         │ 1570 / 70      │                               │
# │ 2000 / 100           │ 0         │ 3130 / 160     │                               │
# │ 5000 / 5000          │ 0         │ 5000 / 5000    │ the 10000 MB maximum          │
# │ 1000 / 40            │ 1         │ 930 / 70       │ download shortened to fit     │
# │ 5000 / 5000          │ 1         │ 500 / 500      │ both shortened to fit         │
# │ 0 / 0                │ 0         │ 50 / 50        │ a failed direction: floor     │
# └──────────────────────┴───────────┴────────────────┴───────────────────────────────┘
# fmt: off
LIMIT_CASES: list[tuple[str, tuple[float, float] | None, int, tuple[int, int]]] = [
    ("first test",          None,           0, (250, 250)),
    ("100/10",              (100.0, 10.0),  0, (160, 50)),
    ("300/20",              (300.0, 20.0),  0, (470, 50)),
    ("1000/40",             (1000.0, 40.0), 0, (1570, 70)),
    ("2000/100",            (2000.0, 100.0), 0, (3130, 160)),
    ("past the maximum",    (5000.0, 5000.0), 0, (5000, 5000)),
    ("budget fits upload",  (1000.0, 40.0), 1, (930, 70)),
    ("budget fits neither", (5000.0, 5000.0), 1, (500, 500)),
    ("no throughput",       (0.0, 0.0),     0, (50, 50)),
]
# fmt: on


@pytest.mark.parametrize("description,speeds,budget_gb,expected", LIMIT_CASES, ids=[c[0] for c in LIMIT_CASES])
def test_automatic_limit(
    description: str, speeds: tuple[float, float] | None, budget_gb: int, expected: tuple[int, int]
) -> None:
    """Sized for a full test at the last speeds, never past the budget."""
    last = _result(*speeds) if speeds else None
    limit = automatic_limit(last, budget_gb)
    assert (limit.download_mb, limit.upload_mb) == expected
    if budget_gb:
        assert limit.total_mb <= budget_gb * 1000


# Most a test may use and the 30-day budget -> days between automatic tests. The budget holds
# k tests at their limit; tests are spaced so no 30 days hold more than k, even when each starts
# anywhere in its 4-hour window or a clock change moves it an hour, so the budget never refuses
# one. Weekly without a budget.
# ┌──────────────┬───────────┬────┬──────┐
# │ limit MB     │ budget GB │ k  │ days │
# ├──────────────┼───────────┼────┼──────┤
# │ 210          │ 0         │    │ 7    │
# │ 210          │ 10        │ 47 │ 1    │
# │ 520          │ 10        │ 19 │ 2    │
# │ 1640         │ 10        │ 6  │ 6    │
# │ 1640         │ 50        │ 30 │ 2    │ daily could fit 31 in 30 days
# │ 1640         │ 51        │ 31 │ 1    │
# │ 3290         │ 10        │ 3  │ 11   │
# │ 3290         │ 50        │ 15 │ 3    │
# │ 1000         │ 1         │ 1  │ 31   │
# │ 1100         │ 1         │ 0  │ none │ no test fits
# └──────────────┴───────────┴────┴──────┘
# fmt: off
EVERY_CASES: list[tuple[int, int, int | None]] = [
    (210,  0,  7),
    (210,  10, 1),
    (520,  10, 2),
    (1640, 10, 6),
    (1640, 50, 2),
    (1640, 51, 1),
    (3290, 10, 11),
    (3290, 50, 3),
    (1000, 1,  31),
    (1100, 1,  None),
]
# fmt: on

SLACK_H = 5  # the 4-hour start window, and an hour for a clock change


@pytest.mark.parametrize("limit_mb,budget_gb,expected", EVERY_CASES)
def test_every_days(limit_mb: int, budget_gb: int, expected: int | None) -> None:
    """At this spacing, the most tests any 30 days can hold, each at its limit, fit the budget."""
    days = every_days(DataLimit.even(limit_mb), budget_gb)
    assert days == expected
    if budget_gb and days:
        # n tests on nights `days` apart span at least (n - 1) * days * 24 - SLACK_H hours.
        most = 1 + (30 * 24 + SLACK_H - 1) // (days * 24)
        assert most == most_tests(days)
        assert most * limit_mb <= budget_gb * 1000


# Days between automatic tests -> the most any 30 days can hold, with the window and a clock change.
# fmt: off
MOST_CASES: list[tuple[int, int]] = [(1, 31), (2, 16), (6, 6), (7, 5), (30, 2), (31, 1)]
# fmt: on


@pytest.mark.parametrize("days,expected", MOST_CASES)
def test_most_tests(days: int, expected: int) -> None:
    """What the setup screen multiplies by the limit to show the most 30 days can use."""
    assert most_tests(days) == expected


# ┌──────────────────────┬──────────┐
# │ line (Mbit/s)        │ MB       │
# ├──────────────────────┼──────────┤
# │ 100 / 10             │ 137.5    │
# │ 1000 / 40            │ 1300     │
# └──────────────────────┴──────────┘
FULL_CASES: list[tuple[float, float, float]] = [(100.0, 10.0, 137.5), (1000.0, 40.0, 1300.0)]


@pytest.mark.parametrize("down,up,expected", FULL_CASES)
def test_full_test_mb(down: float, up: float, expected: float) -> None:
    """A full test moves each direction's speed for the whole window: 1.25 MB per Mbit/s."""
    assert full_test_mb(down, up) == pytest.approx(expected)


def test_even_split() -> None:
    """A data limit set by hand is split evenly between the directions."""
    assert DataLimit.even(500) == DataLimit(250, 250)
    assert DataLimit.even(500).total_mb == 500
