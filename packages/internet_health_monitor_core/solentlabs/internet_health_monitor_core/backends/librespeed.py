"""LibreSpeed backend: the public server list and its PHP endpoints (REFERENCES.md § R20).

IHM sends no telemetry; it only fetches the list, probes each server once
to choose the fastest, and tests against that one.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Literal

import aiohttp

from ..speed_test import SpeedTestError, SpeedTestResult, Transfer
from ._http import HEADERS, REQUEST_TIMEOUT, HttpServer, measure, probe

SERVER_LIST_URL = "https://librespeed.org/backend-servers/servers.php"
# garbage.php sends this many 1 MiB chunks per request (the official client's size, R20).
CHUNKS_PER_REQUEST = 100
# Bytes per upload request: under nginx's default 1 MB body limit, which volunteer servers
# may keep; one listed server refused 8 MB with 413 (seen 2026-11-19).
UPLOAD_BYTES = 1_000_000


def _base(entry: dict[str, Any]) -> str:
    """A listed server's base URL; one without a scheme ("//host") gets https."""
    base = str(entry["server"])
    return "https:" + base if base.startswith("//") else base


def usable(entry: dict[str, Any], require_tls: bool) -> bool:
    """A complete entry over https (http only when tests allow it): a tampered list cannot aim load at a LAN device."""
    if not all(entry.get(k) for k in ("server", "dlURL", "ulURL", "pingURL")):
        return False
    return _base(entry).startswith("https://") or (not require_tls and _base(entry).startswith("http://"))


def _url(base: str, path: str, query: str = "") -> str:
    """An endpoint of a listed server; paths are relative to its base URL."""
    url = f"{base.rstrip('/')}/{path.lstrip('/')}"
    bust = f"r={random.random()}"  # noqa: S311  # cache busting, as the official client does; not security
    extra = f"{query}&{bust}" if query else bust
    return f"{url}{'&' if '?' in url else '?'}{extra}"


def _server(entry: dict[str, Any]) -> HttpServer:
    """The HttpServer for one list entry."""
    base = _base(entry)
    return HttpServer(
        name=str(entry.get("name") or base),
        download_url=lambda _: _url(base, entry["dlURL"], f"ckSize={CHUNKS_PER_REQUEST}"),
        upload_url=lambda: _url(base, entry["ulURL"]),
        probe_url=lambda: _url(base, entry["pingURL"]),
        upload_bytes=UPLOAD_BYTES,
    )


class LibreSpeedBackend:
    """Download, upload and latency against the fastest public LibreSpeed server."""

    name: Literal["librespeed"] = "librespeed"

    def __init__(self, server_list_url: str = SERVER_LIST_URL, require_tls: bool = True) -> None:
        """Use the given server list; tests point it at an in-process server and allow http."""
        self._list_url = server_list_url
        self._require_tls = require_tls

    async def _fastest(self, session: aiohttp.ClientSession) -> HttpServer:
        """Probe every listed server once, concurrently; return the quickest to answer."""
        async with session.get(self._list_url, headers=HEADERS, timeout=REQUEST_TIMEOUT) as resp:
            resp.raise_for_status()
            entries = await resp.json(content_type=None)
        servers = [_server(e) for e in entries if usable(e, self._require_tls)]
        if not servers:
            raise SpeedTestError("LibreSpeed's server list is empty")
        times = await asyncio.gather(*(probe(session, s) for s in servers), return_exceptions=True)
        answered = [(t, s) for t, s in zip(times, servers, strict=True) if isinstance(t, float)]
        if not answered:
            raise SpeedTestError("no LibreSpeed server answered")
        return min(answered, key=lambda pair: pair[0])[1]

    async def run(self, session: aiohttp.ClientSession, max_bytes: int, transfer: Transfer) -> SpeedTestResult:
        """Run one test."""
        return await measure(session, self.name, await self._fastest(session), max_bytes, transfer)
