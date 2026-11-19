"""Reachability: confirm before turning off, re-check fast while off, nothing extra while up (ADR-012)."""

from __future__ import annotations

import pytest

from solentlabs.internet_health_monitor_core.reachability import Reachability
from solentlabs.internet_health_monitor_core.timing import (
    REACHABILITY_CONFIRM_INTERVAL_S,
    REACHABILITY_DOWN_RECHECK_S,
)

CONFIRM = REACHABILITY_CONFIRM_INTERVAL_S
RECHECK = REACHABILITY_DOWN_RECHECK_S

# ┌──────────────────────────────┬──────────────────────────────────────────┬──────────────────────────────────────┐
# │ results, oldest first        │ (shown, next check in s) after each      │ description                          │
# ├──────────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────┤
# │ ok, ok                       │ on/-, on/-                               │ healthy: no extra checks             │
# │ ok, fail, ok                 │ on/5, on/-                               │ one lost packet never shows          │
# │ ok, fail, fail, fail         │ on/5, on/5, off/10                       │ three failures in a row: off         │
# │ ok, fail×3, fail, ok         │ ..., off/10, on/-                        │ recovery shows at once               │
# │ fail                         │ unknown/5                                │ first result unconfirmed: unknown    │
# │ fail, fail, fail             │ unknown/5, unknown/5, off/10             │ starts down after confirming         │
# └──────────────────────────────┴──────────────────────────────────────────┴──────────────────────────────────────┘
# fmt: off
UP, ON_5, OFF_10 = (True, None), (True, CONFIRM), (False, RECHECK)
CASES: list[tuple[list[bool], list[tuple[bool | None, float | None]], str]] = [
    ([True, True],                              [UP, UP],                                "healthy"),
    ([True, False, True],                       [UP, ON_5, UP],                          "one_lost_packet"),
    ([True, False, False, False],               [UP, ON_5, ON_5, OFF_10],                "goes_off"),
    ([True, False, False, False, False, True],  [UP, ON_5, ON_5, OFF_10, OFF_10, UP],    "recovers"),
    ([False],                                   [(None, CONFIRM)],                       "first_failure"),
    ([False, False, False],                     [(None, CONFIRM), (None, CONFIRM), OFF_10], "starts_down"),
]
# fmt: on


@pytest.mark.parametrize("results,expected,desc", CASES, ids=[c[2] for c in CASES])
def test_reachability(results: list[bool], expected: list[tuple[bool | None, float | None]], desc: str) -> None:
    """Each result moves the shown state and says when the next quick check is due."""
    target = Reachability()
    seen = []
    for ok in results:
        delay = target.observe(ok)
        seen.append((target.reachable, delay))
    assert seen == expected, desc
