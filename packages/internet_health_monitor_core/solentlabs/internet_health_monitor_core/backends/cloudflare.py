"""Cloudflare backend: speed.cloudflare.com's `__down` and `__up` endpoints (REFERENCES.md § R5).

Results are never posted to Cloudflare's `__results` endpoint.
"""

from __future__ import annotations

import re
from typing import Literal

import aiohttp

from ..speed_test import SpeedTestResult, Transfer
from ._http import HttpServer, measure

BASE_URL = "https://speed.cloudflare.com"
DOWNLOAD_BYTES = 25_000_000

# Cloudflare reports its own processing time; its client subtracts it from each round trip (R5).
_REQUEST_DURATION = re.compile(r"cfReq(?:uest)?Dur(?:ation)?;\s*dur=([\d.]+)")
_SPEED_DURATION = re.compile(r"cfSpeed\w*;\s*dur=([\d.]+)")


def server_time_ms(resp: aiohttp.ClientResponse) -> float:
    """Server processing time from the `server-timing` header, as Cloudflare's own client reads it."""
    header = resp.headers.get("server-timing", "")
    if match := _REQUEST_DURATION.search(header):
        return float(match.group(1))
    return sum(float(value) for value in _SPEED_DURATION.findall(header))


class CloudflareBackend:
    """Download, upload and latency against speed.cloudflare.com."""

    name: Literal["cloudflare"] = "cloudflare"

    def __init__(self, base_url: str = BASE_URL) -> None:
        """Use *base_url* (tests point it at an in-process server)."""
        self._base = base_url

    async def run(self, session: aiohttp.ClientSession, max_bytes: int, transfer: Transfer) -> SpeedTestResult:
        """Run one test."""
        server = HttpServer(
            name="speed.cloudflare.com",
            download_url=lambda _: f"{self._base}/__down?bytes={DOWNLOAD_BYTES}",
            upload_url=lambda: f"{self._base}/__up",
            probe_url=lambda: f"{self._base}/__down?bytes=0",
            server_time_ms=server_time_ms,
        )
        return await measure(session, self.name, server, max_bytes, transfer)
