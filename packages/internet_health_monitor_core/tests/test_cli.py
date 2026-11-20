"""Tests for the command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from solentlabs.internet_health_monitor_core import cli, mlab_runs
from solentlabs.internet_health_monitor_core.mlab_runs import MlabRun
from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnostics, NetworkDiagnosticsResult
from solentlabs.internet_health_monitor_core.speed_test import DataLimit, SpeedTestError, SpeedTestResult
from solentlabs.internet_health_monitor_core.timing import SPEED_TEST_MLAB_AUTOMATED_WAIT_MAX_S

CLI = cli.__name__

# M-Lab runs already made (hours ago, automated) and who starts this one -> refused, and why (R9).
# fmt: off
MLAB_RULE_CASES: list[tuple[str, list[tuple[float, bool]], bool, str | None]] = [
    ("first automated run",                  [],                True,  None),
    ("4 automated in a day",                 [(1, True)] * 4,   True,  "4 automated"),
    ("a person may test past 4 automated",   [(1, True)] * 4,   False, None),
    ("runs over a day old do not count",     [(25, True)] * 4,  True,  None),
    ("40 in a day stops everyone",           [(1, False)] * 40, False, "40"),
]
# fmt: on

# Platform and environment -> where the command line keeps its state.
# fmt: off
STATE_DIR_CASES: list[tuple[str, str, dict[str, str], str]] = [
    ("Linux, XDG set",  "linux", {"XDG_STATE_HOME": "/xdg"},     "/xdg/internet-health-monitor"),
    ("Linux default",   "linux", {},                             "~/.local/state/internet-health-monitor"),
    ("Windows",         "win32", {"LOCALAPPDATA": "C:/AppData"}, "C:/AppData/internet-health-monitor"),
    ("Windows default", "win32", {},                             "~/AppData/Local/internet-health-monitor"),
]
# fmt: on

# argv -> (dns_server, ping_count, interval, hop_ownership)
# fmt: off
PARSE_CASES = [
    ("defaults",      [],                                   ("auto", 3, None, False)),
    ("dns server",    ["--dns-server", "1.1.1.1"],          ("1.1.1.1", 3, None, False)),
    ("ping count",    ["--ping-count", "5"],                ("auto", 5, None, False)),
    ("interval",      ["--interval", "60"],                 ("auto", 3, 60, False)),
    ("hop ownership", ["--hop-ownership"],                  ("auto", 3, None, True)),
]

# argv rejected by the parser
REJECT_CASES = [
    ("ping count 0",     ["--ping-count", "0"]),
    ("ping count 11",    ["--ping-count", "11"]),
    ("interval 0",       ["--interval", "0"]),
    ("interval 3601",    ["--interval", "3601"]),
    ("non-number",       ["--ping-count", "three"]),
]
# fmt: on


def _result() -> NetworkDiagnosticsResult:
    """Return a minimal result."""
    return NetworkDiagnosticsResult(
        timestamp=1.0,
        gateway_ip="192.168.1.1",
        gateway_reachable=True,
        gateway_latency_ms=1.5,
        gateway_jitter_ms=None,
        packet_loss_percent=0.0,
        packets_sent=3,
        packets_received=3,
    )


@pytest.mark.parametrize(("description", "argv", "expected"), PARSE_CASES, ids=[c[0] for c in PARSE_CASES])
def test_parse(description: str, argv: list[str], expected: tuple[str, int, int | None, bool]) -> None:
    """Options map to the diagnostics config and poll interval; ownership is off unless asked."""
    args = cli.build_parser().parse_args(argv)
    assert (args.dns_server, args.ping_count, args.interval, args.hop_ownership) == expected


@pytest.mark.parametrize(("description", "argv"), REJECT_CASES, ids=[c[0] for c in REJECT_CASES])
def test_parse_rejects(description: str, argv: list[str]) -> None:
    """Out-of-range values match the integration's limits and are refused."""
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(argv)


async def test_single_poll_prints_one_json_line() -> None:
    """Without --interval, one poll runs and its result is one JSON line."""
    out = io.StringIO()
    args = argparse.Namespace(dns_server="auto", ping_count=3, interval=None, hop_ownership=False)
    with patch.object(NetworkDiagnostics, "run_diagnostics", AsyncMock(return_value=_result())):
        await cli.run(args, out)

    lines = out.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["gateway_latency_ms"] == 1.5


async def test_interval_polls_until_stopped() -> None:
    """With --interval, one diagnostics instance keeps polling, one line per poll."""

    class StopLoopError(Exception):
        """Ends the loop in the test."""

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise StopLoopError

    out = io.StringIO()
    args = argparse.Namespace(dns_server="auto", ping_count=3, interval=60, hop_ownership=False)
    with (
        patch.object(NetworkDiagnostics, "run_diagnostics", AsyncMock(return_value=_result())),
        patch.object(asyncio, "sleep", fake_sleep),
        pytest.raises(StopLoopError),
    ):
        await cli.run(args, out)

    assert len(out.getvalue().splitlines()) == 2
    assert sleeps == [60, 60]


def test_main_exits_zero_on_ctrl_c() -> None:
    """Ctrl-C stops a running monitor cleanly."""
    with patch.object(cli, "run", side_effect=KeyboardInterrupt):
        assert cli.main(["--interval", "60"]) == 0


# (--interval, --ping-count) -> accepted? A poll must fit in the interval.
# fmt: off
INTERVAL_FIT_CASES = [
    ("1 ping fits 10 s",   ["--interval", "10", "--ping-count", "1"],  True),
    ("10 pings need 50 s", ["--interval", "20", "--ping-count", "10"], False),
    ("default fits 60 s",  ["--interval", "60"],                       True),
]
# fmt: on


@pytest.mark.parametrize(
    ("description", "argv", "accepted"), INTERVAL_FIT_CASES, ids=[c[0] for c in INTERVAL_FIT_CASES]
)
def test_interval_must_fit_a_poll(description: str, argv: list[str], accepted: bool) -> None:
    """An interval shorter than a poll's worst case is refused before anything runs."""
    with patch.object(cli, "run", AsyncMock()):
        if accepted:
            assert cli.main(argv) == 0
        else:
            with pytest.raises(SystemExit):
                cli.main(argv)


# ┌──────────────────────────────────────────────┬───────────────────────────────────────────┐
# │ argv                                         │ rejected because                          │
# ├──────────────────────────────────────────────┼───────────────────────────────────────────┤
# │ --speed-test mlab                            │ no consent to M-Lab publishing the IP     │
# │ --speed-test cloudflare --interval 60        │ a speed test runs once                    │
# │ --speed-test ookla                           │ not a backend                             │
# │ --data-limit 99                              │ below the minimum                         │
# └──────────────────────────────────────────────┴───────────────────────────────────────────┘
# fmt: off
SPEED_REJECT_CASES: list[tuple[list[str], str]] = [
    (["--speed-test", "mlab"],                            "mlab-consent"),
    (["--speed-test", "cloudflare", "--interval", "60"],  "runs once"),
    (["--speed-test", "ookla"],                           "invalid choice"),
    (["--data-limit", "99"],                              "must be 100"),
]
# fmt: on


@pytest.mark.parametrize("argv,message", SPEED_REJECT_CASES, ids=[c[1] for c in SPEED_REJECT_CASES])
def test_speed_test_arguments_rejected(argv: list[str], message: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Bad speed test arguments exit with a usage error naming the problem."""
    with pytest.raises(SystemExit):
        cli.main(argv)
    assert message in capsys.readouterr().err


def test_speed_test_prints_result_or_reason() -> None:
    """A speed test prints its result as JSON; a failure prints the reason and exits 1."""
    result = SpeedTestResult("mlab", "s", 100.0, 10.0, 12.0, 40.0, 300.0, 140.0, 1.0)
    with patch.object(cli, "run_speed_test", AsyncMock(return_value=result)) as run:
        assert cli.main(["--speed-test", "mlab", "--mlab-consent", "--data-limit", "200"]) == 0
    assert run.call_args.args[0] == "mlab" and run.call_args.args[2] == DataLimit(100, 100)  # split evenly

    out, err = io.StringIO(), io.StringIO()
    args = cli.build_parser().parse_args(["--speed-test", "cloudflare"])
    with patch.object(cli, "run_speed_test", AsyncMock(side_effect=SpeedTestError("no route"))):
        assert asyncio.run(cli.speed_test(args, out, err)) == 1
    assert "no route" in err.getvalue()

    with patch.object(cli, "run_speed_test", AsyncMock(return_value=result)):
        assert asyncio.run(cli.speed_test(args, out, err)) == 0
    assert json.loads(out.getvalue())["download_mbps"] == 100.0


class _Terminal(io.StringIO):
    """Standard input that is a terminal: a person typed the command."""

    def isatty(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def state_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep run state in the test's directory, with a person at the terminal unless a test says otherwise."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "stdin", _Terminal())
    return tmp_path


def _runs_file() -> Path:
    return mlab_runs.state_dir() / mlab_runs.STATE_FILE


def _mlab(argv: list[str] | None = None) -> list[str]:
    return ["--speed-test", "mlab", "--mlab-consent", *(argv or [])]


@pytest.mark.parametrize("description,prior,automated,refused", MLAB_RULE_CASES, ids=[c[0] for c in MLAB_RULE_CASES])
def test_mlab_rules(description: str, prior: list[tuple[float, bool]], automated: bool, refused: str | None) -> None:
    """At most 4 automated runs and 40 in all in any 24 hours, as M-Lab asks of each client (R9)."""
    now = 1_000_000.0
    runs = [MlabRun(now - hours * 3600, was_automated) for hours, was_automated in prior]
    reason = mlab_runs.refusal(runs, now, automated=automated)
    assert (reason is None) if refused is None else (reason is not None and refused in reason)


@pytest.mark.parametrize("description,platform,env,expected", STATE_DIR_CASES, ids=[c[0] for c in STATE_DIR_CASES])
def test_state_dir(
    description: str, platform: str, env: dict[str, str], expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The user's state directory for the platform."""
    for name in ("XDG_STATE_HOME", "LOCALAPPDATA"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(sys, "platform", platform)
    assert mlab_runs.state_dir() == Path(expected).expanduser()


def test_automated_mlab_run_waits_at_random_and_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Started by cron or a script (no terminal): recorded as automated, then a random wait before the test."""
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    result = SpeedTestResult("mlab", "s", 100.0, 10.0, 12.0, 40.0, 300.0, 140.0, 1.0)
    with (
        patch.object(cli, "run_speed_test", AsyncMock(return_value=result)),
        patch(f"{CLI}.random.uniform", return_value=1234.0) as uniform,
        patch(f"{CLI}.asyncio.sleep", AsyncMock()) as sleep,
    ):
        assert cli.main(_mlab()) == 0
    assert uniform.call_args.args == (0, SPEED_TEST_MLAB_AUTOMATED_WAIT_MAX_S)
    sleep.assert_awaited_once_with(1234.0)
    assert [run.automated for run in mlab_runs.load(_runs_file())] == [True]


def test_person_mlab_run_starts_at_once() -> None:
    """Typed at a terminal: recorded as a person's run, no wait."""
    result = SpeedTestResult("mlab", "s", 100.0, 10.0, 12.0, 40.0, 300.0, 140.0, 1.0)
    with (
        patch.object(cli, "run_speed_test", AsyncMock(return_value=result)),
        patch(f"{CLI}.asyncio.sleep", AsyncMock()) as sleep,
    ):
        assert cli.main(_mlab()) == 0
    sleep.assert_not_awaited()
    assert [run.automated for run in mlab_runs.load(_runs_file())] == [False]


def test_mlab_run_past_the_limit_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fifth automated run in a day sends nothing and exits 1 with the reason; old runs are dropped on save."""
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    now = time.time()
    mlab_runs.save(_runs_file(), [MlabRun(now - 3600, True)] * 4 + [MlabRun(now - 30 * 3600, True)])
    with (
        patch.object(cli, "run_speed_test", AsyncMock()) as run,
        patch(f"{CLI}.asyncio.sleep", AsyncMock()),  # fails fast, not after a real wait, if not refused
    ):
        assert cli.main(_mlab()) == 1
    run.assert_not_called()
    assert "4 automated" in capsys.readouterr().err
    assert len(mlab_runs.load(_runs_file())) == 5  # a refused run is not recorded

    mlab_runs.record(_runs_file(), MlabRun(now, False), now)
    assert len(mlab_runs.load(_runs_file())) == 5  # the day-old run dropped, the new one kept


def test_unreadable_state_counts_as_no_runs() -> None:
    """A missing or damaged file means no recorded runs."""
    path = _runs_file()
    assert mlab_runs.load(path) == []
    path.parent.mkdir(parents=True, exist_ok=True)
    for damaged in ("not json", '{"runs": [{"at": "x"}]}', "[1, 2]"):
        path.write_text(damaged)
        assert mlab_runs.load(path) == []


def test_other_services_keep_no_state() -> None:
    """Only M-Lab has per-client rules; other services leave no file."""
    result = SpeedTestResult("cloudflare", "s", 100.0, 10.0, 12.0, 40.0, 300.0, 140.0, 1.0)
    with patch.object(cli, "run_speed_test", AsyncMock(return_value=result)):
        assert cli.main(["--speed-test", "cloudflare"]) == 0
    assert not _runs_file().exists()
