"""M-Lab's per-client limits for the command line, which keeps no memory between runs otherwise.

M-Lab asks automated clients for at most 4 tests a day at random times, and
every client for at most 40 (REFERENCES.md § R9). The HA integration keeps its
own run history; the command line records M-Lab runs in a small file in the
user's state directory (docs/SPEED_TEST_BACKENDS.md § Running Tests and Limits).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .timing import SPEED_TEST_DAILY_WINDOW_S, SPEED_TEST_MLAB_AUTOMATED_DAILY, SPEED_TEST_MLAB_DAILY

STATE_FILE = "mlab_runs.json"


@dataclass(frozen=True)
class MlabRun:
    """One accepted M-Lab run: when (epoch seconds) and whether a person started it."""

    at: float
    automated: bool


def state_dir() -> Path:
    """The user's state directory: %LOCALAPPDATA% on Windows, else $XDG_STATE_HOME (default ~/.local/state)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    else:
        base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "internet-health-monitor"


def load(path: Path) -> list[MlabRun]:
    """Recorded runs; a missing or damaged file means none."""
    try:
        data = json.loads(path.read_text())
        return [MlabRun(float(run["at"]), bool(run["automated"])) for run in data["runs"]]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def save(path: Path, runs: list[MlabRun]) -> None:
    """Write *runs*, replacing the file in one step so a crash leaves the old one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"runs": [asdict(run) for run in runs]}))
    temp.replace(path)


def _recent(runs: list[MlabRun], now: float) -> list[MlabRun]:
    """Runs inside the last 24 hours."""
    return [run for run in runs if now - run.at < SPEED_TEST_DAILY_WINDOW_S]


def refusal(runs: list[MlabRun], now: float, *, automated: bool) -> str | None:
    """Why a new run may not start, or None when it may."""
    recent = _recent(runs, now)
    if len(recent) >= SPEED_TEST_MLAB_DAILY:
        return f"M-Lab allows {SPEED_TEST_MLAB_DAILY} tests a day per client; try again later"
    if automated and sum(run.automated for run in recent) >= SPEED_TEST_MLAB_AUTOMATED_DAILY:
        return (
            f"M-Lab asks automated clients for at most {SPEED_TEST_MLAB_AUTOMATED_DAILY} automated tests a day; "
            "run it from a terminal, or try again later"
        )
    return None


def record(path: Path, run: MlabRun, now: float) -> None:
    """Add *run*, keeping only the last 24 hours."""
    save(path, [*_recent(load(path), now), run])
