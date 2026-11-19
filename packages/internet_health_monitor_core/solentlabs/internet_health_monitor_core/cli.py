"""Command-line entry point: run diagnostics and print one JSON line per poll."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
from typing import TextIO

from .network_diagnostics import (
    DEFAULT_DNS_SERVER,
    DEFAULT_PING_COUNT,
    NetworkDiagnostics,
    NetworkDiagnosticsConfig,
)

# Same limits as the HA options flow.
PING_COUNT_RANGE = (1, 10)
INTERVAL_RANGE = (10, 3600)


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
    return parser


async def run(args: argparse.Namespace, out: TextIO) -> None:
    """Poll once, or every interval seconds, writing each result as a JSON line."""
    diagnostics = NetworkDiagnostics(
        config=NetworkDiagnosticsConfig(ping_count=args.ping_count, dns_server=args.dns_server)
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
    args = build_parser().parse_args(argv)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(args, sys.stdout))
    return 0
