"""Reachability that confirms before turning off and re-checks fast while off (ADR-012).

Pure logic: the host feeds it each result and schedules the quick check it
asks for. Nothing extra runs while a target is healthy.
"""

from __future__ import annotations

from typing import Literal

from .timing import REACHABILITY_CONFIRM_CHECKS, REACHABILITY_CONFIRM_INTERVAL_S, REACHABILITY_DOWN_RECHECK_S

State = Literal["unknown", "up", "confirming", "down"]


class Reachability:
    """One target (gateway or internet): what to show, and when to check again."""

    def __init__(self) -> None:
        """Nothing is known until the first result."""
        self.state: State = "unknown"
        self.reachable: bool | None = None  # what the sensor shows; unchanged while confirming
        self._failures = 0

    def observe(self, ok: bool) -> float | None:
        """Record a poll or quick-check result; return seconds until the next quick check, or None for none."""
        if ok:
            self.state, self.reachable, self._failures = "up", True, 0
            return None
        if self.state == "down":
            return REACHABILITY_DOWN_RECHECK_S
        self._failures += 1
        if self._failures > REACHABILITY_CONFIRM_CHECKS:
            self.state, self.reachable = "down", False
            return REACHABILITY_DOWN_RECHECK_S
        self.state = "confirming"
        return REACHABILITY_CONFIRM_INTERVAL_S
