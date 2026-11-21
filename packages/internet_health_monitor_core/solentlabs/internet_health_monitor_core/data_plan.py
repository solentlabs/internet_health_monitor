"""How much data a speed test may use, and how often automatic tests fit a budget.

The rules behind .github/README.md § How Much Data Speed Tests Use; hosts show their
working from these, so the user sees why. Each direction runs for
SPEED_TEST_DIRECTION_S, so a full test moves about that many seconds of each
direction's speed: 1.25 MB per Mbit/s.
"""

from __future__ import annotations

import math

from . import timing
from .speed_test import DataLimit, SpeedTestResult

_STEP_MB = 10  # automatic limits are whole multiples of this


def direction_mb(mbps: float) -> float:
    """MB one direction moves in a full window at *mbps*."""
    return mbps * timing.SPEED_TEST_DIRECTION_S / 8


def full_test_mb(download_mbps: float, upload_mbps: float) -> float:
    """MB a full test moves on a line of these speeds."""
    return direction_mb(download_mbps) + direction_mb(upload_mbps)


def _step(mb: float) -> int:
    """Up to the next whole step, within each direction's range."""
    low, high = timing.SPEED_TEST_DATA_LIMIT_MB_MIN // 2, timing.SPEED_TEST_DATA_LIMIT_MB_MAX // 2
    return min(high, max(low, math.ceil(mb / _STEP_MB) * _STEP_MB))


def automatic_limit(last: SpeedTestResult | None, budget_gb: int = 0) -> DataLimit:
    """Each direction's limit for a full test at the last test's speeds, plus a margin, within the budget.

    With no last test, the default limit, split evenly: the first test measures the line.
    A budget too small for both directions keeps the smaller one whole where it can.
    """
    if last is None:
        limit = DataLimit.even(timing.SPEED_TEST_DATA_LIMIT_MB_DEFAULT)
    else:
        margin = timing.SPEED_TEST_AUTO_LIMIT_MARGIN
        limit = DataLimit(
            _step(direction_mb(last.download_mbps) * margin), _step(direction_mb(last.upload_mbps) * margin)
        )
    budget_mb = budget_gb * 1000
    if not budget_mb or limit.total_mb <= budget_mb:
        return limit
    half = budget_mb // 2 // _STEP_MB * _STEP_MB
    if limit.download_mb <= limit.upload_mb:
        down = min(limit.download_mb, half)
        return DataLimit(down, (budget_mb - down) // _STEP_MB * _STEP_MB)
    up = min(limit.upload_mb, half)
    return DataLimit((budget_mb - up) // _STEP_MB * _STEP_MB, up)


# Hours by which tests on nights d days apart can fall short of d days: the start window, and
# an hour for a clock change.
_SLACK_H = timing.SPEED_TEST_AUTO_WINDOW_S // 3600 + 1
_WINDOW_H = timing.SPEED_TEST_BUDGET_WINDOW_S // 3600


def most_tests(days: int) -> int:
    """The most automatic tests any 30 days can hold at this spacing."""
    return 1 + (_WINDOW_H + _SLACK_H - 1) // (days * 24)


def every_days(limit: DataLimit, budget_gb: int) -> int | None:
    """Days between automatic tests: weekly without a budget; else as often as the budget holds every test.

    The budget holds k tests at their limit. Tests are spaced so no 30 days hold more than k,
    though each starts anywhere in its window and a clock change can move it an hour, so the
    budget never refuses one. None when not even one test fits.
    """
    if not budget_gb:
        return timing.SPEED_TEST_AUTO_EVERY_DAYS_NO_BUDGET
    fits = budget_gb * 1000 // limit.total_mb
    if not fits:
        return None
    return max(1, math.ceil((_WINDOW_H + _SLACK_H) / (fits * 24)))
