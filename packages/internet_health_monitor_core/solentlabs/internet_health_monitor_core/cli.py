"""Command-line entry point: run diagnostics and print one JSON line per poll, or run one speed test."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
from typing import TextIO

import aiohttp

from .network_diagnostics import DEFAULT_DNS_SERVER, NetworkDiagnostics, NetworkDiagnosticsConfig
from .speed_test import BACKEND_NAMES, SpeedTestError, run_speed_test
from .timing import (
    DEFAULT_PING_COUNT,
    PING_COUNT_MAX,
    PING_COUNT_MIN,
    SPEED_TEST_DATA_LIMIT_MB_DEFAULT,
    SPEED_TEST_DATA_LIMIT_MB_MAX,
    SPEED_TEST_DATA_LIMIT_MB_MIN,
    steady_poll_bound_s,
)

PING_COUNT_RANGE = (PING_COUNT_MIN, PING_COUNT_MAX)
# The lower bound also depends on --ping-count: a poll must finish before the next.
INTERVAL_RANGE = (1, 3600)


def _int_in(low: int, high: int) -> type[int]:
    """Return an argparse type that accepts integers from low to high."""

    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{value!r} is not a whole number") from None
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"must be {low} to {high}")
        return number

    return parse  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="internet-health-monitor",
        description="Measure gateway, hop and DNS latency, jitter and loss. Prints JSON.",
    )
    parser.add_argument("--dns-server", default=DEFAULT_DNS_SERVER, help="DNS server to time, or 'auto'")
    parser.add_argument("--ping-count", type=_int_in(*PING_COUNT_RANGE), default=DEFAULT_PING_COUNT)
    parser.add_argument(
        "--interval",
        type=_int_in(*INTERVAL_RANGE),
        default=None,
        help="seconds between polls; without it, poll once and exit",
    )
    parser.add_argument(
        "--hop-ownership",
        action="store_true",
        help="look up each public hop's network operator (sends hop IPs to Team Cymru)",
    )
    parser.add_argument(
        "--speed-test",
        choices=BACKEND_NAMES,
        help="run one speed test with this service and exit (docs/SPEED_TEST_BACKENDS.md); the service sees your IP",
    )
    parser.add_argument(
        "--data-limit",
        type=_int_in(SPEED_TEST_DATA_LIMIT_MB_MIN, SPEED_TEST_DATA_LIMIT_MB_MAX),
        default=SPEED_TEST_DATA_LIMIT_MB_DEFAULT,
        help="most MB one speed test may use, both directions together",
    )
    parser.add_argument(
        "--mlab-consent",
        action="store_true",
        help="required for --speed-test mlab: M-Lab publishes every result with your IP address, permanently",
    )
    return parser


async def speed_test(args: argparse.Namespace, out: TextIO, err: TextIO) -> int:
    """Run one speed test; print the result as JSON, or the reason it failed to *err*."""
    async with aiohttp.ClientSession() as session:
        try:
            result = await run_speed_test(args.speed_test, session, data_limit_mb=args.data_limit)
        except SpeedTestError as error:
            err.write(f"speed test failed: {error} (used {error.downloaded_mb} MB down, {error.uploaded_mb} MB up)\n")
            return 1
    out.write(json.dumps(result.to_dict()) + "\n")
    return 0


async def run(args: argparse.Namespace, out: TextIO) -> None:
    """Poll once, or every interval seconds, writing each result as a JSON line."""
    diagnostics = NetworkDiagnostics(
        config=NetworkDiagnosticsConfig(
            ping_count=args.ping_count, dns_server=args.dns_server, hop_ownership=args.hop_ownership
        )
    )
    while True:
        result = await diagnostics.run_diagnostics()
        out.write(json.dumps(result.to_dict()) + "\n")
        out.flush()
        if args.interval is None:
            return
        await asyncio.sleep(args.interval)


def main(argv: list[str] | None = None) -> int:
    """Run the command line and return the exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.interval is not None and args.interval < steady_poll_bound_s(args.ping_count):
        parser.error(
            f"--interval {args.interval} is shorter than a poll can take with "
            f"--ping-count {args.ping_count} ({steady_poll_bound_s(args.ping_count)} s)"
        )
    if args.speed_test:
        if args.interval is not None:
            parser.error("--speed-test runs once; it cannot be combined with --interval")
        if args.speed_test == "mlab" and not args.mlab_consent:
            parser.error("M-Lab publishes every result with your IP address, permanently; add --mlab-consent to agree")
        return asyncio.run(speed_test(args, sys.stdout, sys.stderr))
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(args, sys.stdout))
    return 0
