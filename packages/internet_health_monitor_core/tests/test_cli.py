"""Tests for the command-line entry point."""

from __future__ import annotations

import asyncio
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from solentlabs.internet_health_monitor_core import cli
from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnosticsResult
from solentlabs.internet_health_monitor_core.speed_test import SpeedTestError, SpeedTestResult

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
    args = SimpleNamespace(dns_server="auto", ping_count=3, interval=None, hop_ownership=False)
    with patch.object(cli.NetworkDiagnostics, "run_diagnostics", AsyncMock(return_value=_result())):
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
    args = SimpleNamespace(dns_server="auto", ping_count=3, interval=60, hop_ownership=False)
    with (
        patch.object(cli.NetworkDiagnostics, "run_diagnostics", AsyncMock(return_value=_result())),
        patch.object(cli.asyncio, "sleep", fake_sleep),
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
    assert run.call_args.args[0] == "mlab" and run.call_args.kwargs["data_limit_mb"] == 200

    out, err = io.StringIO(), io.StringIO()
    args = cli.build_parser().parse_args(["--speed-test", "cloudflare"])
    with patch.object(cli, "run_speed_test", AsyncMock(side_effect=SpeedTestError("no route"))):
        assert asyncio.run(cli.speed_test(args, out, err)) == 1
    assert "no route" in err.getvalue()

    with patch.object(cli, "run_speed_test", AsyncMock(return_value=result)):
        assert asyncio.run(cli.speed_test(args, out, err)) == 0
    assert json.loads(out.getvalue())["download_mbps"] == 100.0
