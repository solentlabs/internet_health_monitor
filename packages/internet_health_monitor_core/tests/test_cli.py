"""Tests for the command-line entry point."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from solentlabs.internet_health_monitor_core import cli
from solentlabs.internet_health_monitor_core.network_diagnostics import NetworkDiagnosticsResult

# argv -> (dns_server, ping_count, interval)
# fmt: off
PARSE_CASES = [
    ("defaults",      [],                                   ("auto", 3, None)),
    ("dns server",    ["--dns-server", "1.1.1.1"],          ("1.1.1.1", 3, None)),
    ("ping count",    ["--ping-count", "5"],                ("auto", 5, None)),
    ("interval",      ["--interval", "60"],                 ("auto", 3, 60)),
]

# argv rejected by the parser
REJECT_CASES = [
    ("ping count 0",     ["--ping-count", "0"]),
    ("ping count 11",    ["--ping-count", "11"]),
    ("interval 9",       ["--interval", "9"]),
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
def test_parse(description: str, argv: list[str], expected: tuple[str, int, int | None]) -> None:
    """Options map to the diagnostics config and poll interval."""
    args = cli.build_parser().parse_args(argv)
    assert (args.dns_server, args.ping_count, args.interval) == expected


@pytest.mark.parametrize(("description", "argv"), REJECT_CASES, ids=[c[0] for c in REJECT_CASES])
def test_parse_rejects(description: str, argv: list[str]) -> None:
    """Out-of-range values match the integration's limits and are refused."""
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(argv)


async def test_single_poll_prints_one_json_line() -> None:
    """Without --interval, one poll runs and its result is one JSON line."""
    out = io.StringIO()
    args = SimpleNamespace(dns_server="auto", ping_count=3, interval=None)
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
    args = SimpleNamespace(dns_server="auto", ping_count=3, interval=60)
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
