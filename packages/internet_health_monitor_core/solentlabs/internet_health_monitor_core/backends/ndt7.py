"""M-Lab NDT7 backend: Locate API v2, then the ndt7 WebSocket protocol (REFERENCES.md § R9).

M-Lab publishes every result with the client's public IP address. Hosts must
get the user's informed consent before running this backend (ADR-006).
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
from typing import Any, Literal

import aiohttp

from .. import timing
from ..speed_test import CLIENT_NAME, CLIENT_VERSION, SpeedTestError, SpeedTestResult, Transfer, now
from ._http import HEADERS, REQUEST_TIMEOUT, check_status

LOCATE_URL = "https://locate.measurementlab.net/v2/nearest/ndt/ndt7"
PROTOCOL = "net.measurementlab.ndt.v7"
DOWNLOAD_KEY = "wss:///ndt/v7/download"
UPLOAD_KEY = "wss:///ndt/v7/upload"
# Upload messages start at 1 << 13 bytes and double, up to 1 << 24 (R9).
FIRST_MESSAGE = 1 << 13
MAX_MESSAGE = 1 << 24
_PAYLOAD = os.urandom(MAX_MESSAGE)
# ClientWSTimeout is an old-style attrs class whose fields pyright cannot see; mypy checks the call.
WS_TIMEOUT = aiohttp.ClientWSTimeout(
    ws_receive=timing.SPEED_TEST_REQUEST_TIMEOUT_S, ws_close=5.0  # pyright: ignore[reportCallIssue]
)


def _ms(microseconds: float | None) -> float | None:
    """Microseconds (the protocol's unit) to ms."""
    return microseconds / 1000 if microseconds is not None else None


class _Readings:
    """What the server reported during one direction."""

    def __init__(self) -> None:
        self.rtt_us: list[float] = []
        self.min_rtt_us: float | None = None
        self.app_bytes: int | None = None
        self.app_elapsed_us: float | None = None

    def add(self, text: str) -> None:
        """Record one Measurement message; a message that is not JSON is ignored."""
        try:
            message: dict[str, Any] = json.loads(text)
        except ValueError:
            return
        tcp = message.get("TCPInfo") or {}
        if (rtt := tcp.get("RTT")) is not None:
            self.rtt_us.append(float(rtt))
        if (min_rtt := tcp.get("MinRTT")) is not None:
            self.min_rtt_us = min(float(min_rtt), self.min_rtt_us or float(min_rtt))
        app = message.get("AppInfo") or {}
        if app.get("NumBytes") is not None and app.get("ElapsedTime"):
            self.app_bytes, self.app_elapsed_us = int(app["NumBytes"]), float(app["ElapsedTime"])

    def loaded_ms(self) -> float | None:
        """Median smoothed round trip while loaded."""
        return _ms(statistics.median(self.rtt_us)) if self.rtt_us else None


class Ndt7Backend:
    """Download, upload and latency against the nearest M-Lab server."""

    name: Literal["mlab"] = "mlab"

    def __init__(self, locate_url: str = LOCATE_URL, require_tls: bool = True) -> None:
        """Use the given Locate API; tests point it at an in-process server and allow ws://."""
        self._locate = locate_url
        self._require_tls = require_tls

    async def _locate_servers(self, session: aiohttp.ClientSession) -> list[dict[str, Any]]:
        """Candidate servers, nearest first; 204 is M-Lab's rate-limit or no-capacity reply."""
        params = {"client_name": CLIENT_NAME, "client_version": CLIENT_VERSION}
        async with session.get(
            self._locate, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=False
        ) as resp:
            if resp.status == 204:
                raise SpeedTestError("M-Lab declined the test: daily limit reached or no capacity; try later")
            check_status(resp)
            reply = await resp.json(content_type=None)
        results = [r for r in reply.get("results") or [] if DOWNLOAD_KEY in r.get("urls", {})]
        if not results:
            raise SpeedTestError("M-Lab's Locate API returned no servers")
        return results

    async def _download(
        self, session: aiohttp.ClientSession, url: str, max_bytes: int, transfer: Transfer
    ) -> tuple[float, int, _Readings]:
        """Receive until the server closes or *max_bytes* arrive; return (Mbit/s, bytes, readings)."""
        loop = asyncio.get_running_loop()
        readings, total = _Readings(), 0
        async with session.ws_connect(
            url, protocols=(PROTOCOL,), headers=HEADERS, max_msg_size=0, timeout=WS_TIMEOUT
        ) as ws:
            start = loop.time()
            async for msg in ws:
                if msg.type is aiohttp.WSMsgType.BINARY:
                    total += len(msg.data)
                    transfer.downloaded += len(msg.data)
                elif msg.type is aiohttp.WSMsgType.TEXT:
                    total += len(msg.data)
                    transfer.downloaded += len(msg.data)
                    readings.add(msg.data)
                if loop.time() - start >= timing.SPEED_TEST_NDT7_MAX_S or total >= max_bytes:
                    break
            elapsed = loop.time() - start
        if total <= 0 or elapsed <= 0:
            raise SpeedTestError("M-Lab server sent no data")
        return total * 8 / 1e6 / elapsed, total, readings

    async def _upload(
        self, session: aiohttp.ClientSession, url: str, max_bytes: int, transfer: Transfer
    ) -> tuple[float, int, _Readings]:
        """Send for SPEED_TEST_DIRECTION_S or *max_bytes*; throughput is what the server says it received."""
        loop = asyncio.get_running_loop()
        readings, sent, size = _Readings(), 0, FIRST_MESSAGE
        async with session.ws_connect(
            url, protocols=(PROTOCOL,), headers=HEADERS, max_msg_size=0, timeout=WS_TIMEOUT
        ) as ws:

            async def read() -> None:
                async for msg in ws:
                    if msg.type is aiohttp.WSMsgType.TEXT:
                        readings.add(msg.data)

            reader = asyncio.create_task(read())
            start = loop.time()
            try:
                while loop.time() - start < timing.SPEED_TEST_DIRECTION_S and sent < max_bytes and not ws.closed:
                    await ws.send_bytes(_PAYLOAD[:size])
                    sent += size
                    transfer.uploaded += size
                    # Bytes sent so far stand in for the protocol's "queued bytes" (R9).
                    if size < MAX_MESSAGE and size < sent // 16:
                        size *= 2
                elapsed = loop.time() - start
                # close() discards messages still arriving, so let the server report what it
                # received (or close the test itself) first.
                await asyncio.wait({reader}, timeout=timing.SPEED_TEST_NDT7_CLOSE_GRACE_S)
                await ws.close()
            finally:
                reader.cancel()
        if readings.app_bytes and readings.app_elapsed_us:
            return readings.app_bytes * 8 / readings.app_elapsed_us, sent, readings
        if sent <= 0 or elapsed <= 0:
            raise SpeedTestError("M-Lab server accepted no data")
        return sent * 8 / 1e6 / elapsed, sent, readings

    async def run(self, session: aiohttp.ClientSession, max_bytes: int, transfer: Transfer) -> SpeedTestResult:
        """Run one test, falling back to the next candidate if a server cannot be reached."""
        started = now()
        last_error: Exception | None = None
        for candidate in await self._locate_servers(session):
            urls = candidate["urls"]
            if self._require_tls and not all(urls.get(k, "").startswith("wss://") for k in (DOWNLOAD_KEY, UPLOAD_KEY)):
                last_error = SpeedTestError(f"{candidate.get('machine')} offered no wss:// URL")
                continue
            try:
                download_mbps, down_bytes, down = await self._download(session, urls[DOWNLOAD_KEY], max_bytes, transfer)
            except (aiohttp.ClientError, OSError) as err:
                last_error = err
                continue
            upload_mbps, up_bytes, up = await self._upload(session, urls[UPLOAD_KEY], max_bytes, transfer)
            city = (candidate.get("location") or {}).get("city")
            machine = str(candidate.get("machine", "M-Lab"))
            return SpeedTestResult(
                backend=self.name,
                server=f"{machine} ({city})" if city else machine,
                download_mbps=round(download_mbps, 2),
                upload_mbps=round(upload_mbps, 2),
                idle_latency_ms=_round(_ms(down.min_rtt_us)),
                download_latency_ms=_round(down.loaded_ms()),
                upload_latency_ms=_round(up.loaded_ms()),
                data_used_mb=round((down_bytes + up_bytes) / 1e6, 1),
                started_at=started,
                downloaded_mb=round(down_bytes / 1e6, 1),
                uploaded_mb=round(up_bytes / 1e6, 1),
            )
        raise SpeedTestError(f"no M-Lab server could be reached: {last_error}")


def _round(value: float | None) -> float | None:
    """Round a latency to 0.1 ms, keeping None."""
    return round(value, 1) if value is not None else None
