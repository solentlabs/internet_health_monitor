"""Tests that Core's timing constants fit together (ADR-007)."""

from __future__ import annotations

import pytest

from solentlabs.internet_health_monitor_core import timing

# ping count -> worst-case regular poll, seconds
# fmt: off
BOUND_CASES = [
    (1,  5),   # one ping: 2 s wait + 3 s grace; DNS (5 s) runs alongside
    (3,  15),
    (10, 50),
]
# fmt: on


@pytest.mark.parametrize(("ping_count", "expected"), BOUND_CASES)
def test_steady_poll_bound(ping_count: int, expected: int) -> None:
    """Targets run in parallel; each target's pings run in sequence."""
    assert timing.steady_poll_bound_s(ping_count) == expected


def test_largest_poll_fits_the_interval() -> None:
    """Even at the maximum ping count, a poll finishes before the next is due."""
    assert timing.steady_poll_bound_s(timing.PING_COUNT_MAX) < timing.POLL_INTERVAL_S


def test_default_ping_count_in_range() -> None:
    """The default sits inside the range the forms accept."""
    assert timing.PING_COUNT_MIN <= timing.DEFAULT_PING_COUNT <= timing.PING_COUNT_MAX
