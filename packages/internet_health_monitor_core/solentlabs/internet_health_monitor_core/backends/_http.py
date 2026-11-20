"""The measuring engine shared by HTTP backends (docs/SPEED_TEST_BACKENDS.md § How IHM Measures).

A backend describes its server as an `HttpServer` (where to download, upload
and probe); `measure` does the rest, the same way for every provider.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import statistics
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .. import timing
from ..speed_test import USER_AGENT, BackendName, DataLimit, EndedBy, SpeedTestError, SpeedTestResult, Transfer, now

HEADERS = {"User-Agent": USER_AGENT}
STREAMS = 4
IDLE_PROBES = 10
READ_CHUNK = 64 * 1024
# Bytes per upload request; streams post one after another until time is up.
UPLOAD_REQUEST_BYTES = 8 * 1024 * 1024
_BLOCK = os.urandom(READ_CHUNK)
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=timing.SPEED_TEST_REQUEST_TIMEOUT_S)
# Load streams run until stopped; only a stalled read times out.
STREAM_TIMEOUT = aiohttp.ClientTimeout(total=None, sock_read=timing.SPEED_TEST_REQUEST_TIMEOUT_S)
# aiohttp starts the read clock while a body is still being sent, and on a slow uplink one
# body outlasts any read timeout. The direction's own end cancels the stream instead.
UPLOAD_TIMEOUT = aiohttp.ClientTimeout(total=None, sock_read=None, sock_connect=timing.SPEED_TEST_REQUEST_TIMEOUT_S)


def no_server_time(_: aiohttp.ClientResponse) -> float:
    """Default: the server reports no processing time to subtract."""
    return 0.0


@dataclass(frozen=True)
class HttpServer:
    """Where one test runs. URL functions may add cache-busting parameters per call."""

    name: str
    download_url: Callable[[int], str]  # stream index -> URL returning a large body
    upload_url: Callable[[], str]  # URL accepting a POST body
    probe_url: Callable[[], str]  # URL returning a tiny body quickly
    server_time_ms: Callable[[aiohttp.ClientResponse], float] = field(default=no_server_time)
    probe_headers: dict[str, str] = field(default_factory=dict)  # added to probe requests
    upload_bytes: int | None = None  # bytes per upload request; None: UPLOAD_REQUEST_BYTES


class _Counter:
    """Bytes moved in one direction, against that direction's data limit."""

    def __init__(self, limit: int, transfer: Transfer, direction: str) -> None:
        self.total = 0
        self.limit = limit
        self._transfer = transfer
        self._direction = direction  # the Transfer field this direction adds to

    @property
    def full(self) -> bool:
        """Whether the direction has reached its limit."""
        return self.total >= self.limit

    def add(self, count: int) -> None:
        """Record bytes moved, in this direction and in the test's running tally."""
        self.total += count
        setattr(self._transfer, self._direction, getattr(self._transfer, self._direction) + count)


def check_status(resp: aiohttp.ClientResponse) -> None:
    """Refuse an error or a redirect: requests never follow one, so a server cannot point the load elsewhere."""
    resp.raise_for_status()
    if resp.status >= 300:
        raise aiohttp.ClientResponseError(
            resp.request_info, resp.history, status=resp.status, message="redirect refused"
        )


async def probe(session: aiohttp.ClientSession, server: HttpServer) -> float:
    """One round trip in ms: time to response headers, minus the server's own processing time."""
    loop = asyncio.get_running_loop()
    start = loop.time()
    headers = {**HEADERS, **server.probe_headers}
    async with session.get(server.probe_url(), headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=False) as resp:
        elapsed_ms = (loop.time() - start) * 1000
        check_status(resp)
        await resp.read()
        return max(0.0, elapsed_ms - server.server_time_ms(resp))


async def _idle_latency(session: aiohttp.ClientSession, server: HttpServer) -> float:
    """Median of IDLE_PROBES probes after one warm-up (which also opens the probe connection)."""
    await probe(session, server)
    return statistics.median([await probe(session, server) for _ in range(IDLE_PROBES)])


async def _download_stream(session: aiohttp.ClientSession, server: HttpServer, index: int, counter: _Counter) -> None:
    """Fetch large bodies back to back until cancelled."""
    while True:
        async with session.get(
            server.download_url(index), headers=HEADERS, timeout=STREAM_TIMEOUT, allow_redirects=False
        ) as resp:
            check_status(resp)
            async for chunk in resp.content.iter_chunked(READ_CHUNK):
                counter.add(len(chunk))
                if counter.full:
                    return


async def _upload_body(counter: _Counter, total: int) -> AsyncIterator[bytes]:
    """Up to *total* bytes of random data, sent chunked so it can stop exactly at the data limit.

    Each block counts once the transport takes the next.
    """
    sent = 0
    while sent < total and not counter.full:
        size = min(READ_CHUNK, total - sent)
        yield _BLOCK[:size]
        counter.add(size)
        sent += size


async def _upload_stream(session: aiohttp.ClientSession, server: HttpServer, index: int, counter: _Counter) -> None:
    """Post bodies back to back until cancelled."""
    headers = {**HEADERS, "Content-Type": "application/octet-stream"}
    while not counter.full:
        async with session.post(
            server.upload_url(),
            data=_upload_body(counter, server.upload_bytes or UPLOAD_REQUEST_BYTES),
            headers=headers,
            timeout=UPLOAD_TIMEOUT,
            allow_redirects=False,
        ) as resp:
            check_status(resp)
            await resp.read()


async def _probe_loop(session: aiohttp.ClientSession, server: HttpServer, samples: list[float]) -> None:
    """Probe every SPEED_TEST_PROBE_INTERVAL_S until cancelled; a failed probe is skipped."""
    while True:
        with contextlib.suppress(aiohttp.ClientError, TimeoutError):
            samples.append(await probe(session, server))
        await asyncio.sleep(timing.SPEED_TEST_PROBE_INTERVAL_S)


StreamFn = Callable[[aiohttp.ClientSession, HttpServer, int, _Counter], Coroutine[Any, Any, None]]


async def _run_until(tasks: list[asyncio.Task[None]], counter: _Counter, seconds: float) -> None:
    """Wait *seconds*, or until the limit is reached; a stream that fails ends the test."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while (left := deadline - loop.time()) > 0 and not counter.full:
        done, _ = await asyncio.wait(
            tasks, timeout=min(left, timing.SPEED_TEST_LIMIT_CHECK_S), return_when=asyncio.FIRST_EXCEPTION
        )
        _raise_first(done, counter)


@dataclass(frozen=True)
class _Direction:
    """One direction's reading."""

    mbps: float  # after warm-up
    latency_ms: float | None  # median while loaded
    ended_by: EndedBy
    seconds: float  # how long it was loaded


async def _direction(
    session: aiohttp.ClientSession, server: HttpServer, stream: StreamFn, counter: _Counter
) -> _Direction:
    """Load one direction until its window or data limit ends it."""
    loop = asyncio.get_running_loop()
    start = loop.time()
    samples: list[float] = []
    tasks = [asyncio.create_task(stream(session, server, i, counter)) for i in range(STREAMS)]
    prober = asyncio.create_task(_probe_loop(session, server, samples))
    try:
        await _run_until(tasks, counter, timing.SPEED_TEST_WARMUP_S)
        warm_bytes, warm_time, warm_samples = counter.total, loop.time(), len(samples)
        remaining = timing.SPEED_TEST_DIRECTION_S - timing.SPEED_TEST_WARMUP_S
        await _run_until(tasks, counter, remaining)
        measured, seconds = counter.total - warm_bytes, loop.time() - warm_time
        if measured <= 0:  # limit reached during warm-up: use the whole run
            measured, seconds = counter.total, seconds + timing.SPEED_TEST_WARMUP_S
        loaded_s = loop.time() - start
    finally:
        for task in [*tasks, prober]:
            task.cancel()
        await asyncio.gather(*tasks, prober, return_exceptions=True)
    if measured <= 0:
        raise SpeedTestError(f"{server.name} sent or accepted no data")
    loaded = samples[warm_samples:] or samples
    return _Direction(
        mbps=measured * 8 / 1e6 / seconds,
        latency_ms=statistics.median(loaded) if loaded else None,
        ended_by="data_limit" if counter.full else "time",
        seconds=loaded_s,
    )


def _raise_first(done: set[asyncio.Task[None]], counter: _Counter) -> None:
    """Re-raise a stream's error; a stream may end on its own only at the data limit."""
    for task in done:
        task.result()
        if not counter.full:
            raise SpeedTestError("a load stream ended early")


def _round(value: float | None) -> float | None:
    """Round a latency to 0.1 ms, keeping None."""
    return round(value, 1) if value is not None else None


async def measure(
    session: aiohttp.ClientSession, backend: BackendName, server: HttpServer, limit: DataLimit, transfer: Transfer
) -> SpeedTestResult:
    """Idle latency, then download, then upload, against one server; each direction within its *limit*."""
    started = now()
    idle = await _idle_latency(session, server)
    down = _Counter(limit.download_mb * 1_000_000, transfer, "downloaded")
    up = _Counter(limit.upload_mb * 1_000_000, transfer, "uploaded")
    download = await _direction(session, server, _download_stream, down)
    upload = await _direction(session, server, _upload_stream, up)
    return SpeedTestResult(
        backend=backend,
        server=server.name,
        download_mbps=round(download.mbps, 2),
        upload_mbps=round(upload.mbps, 2),
        idle_latency_ms=round(idle, 1),
        download_latency_ms=_round(download.latency_ms),
        upload_latency_ms=_round(upload.latency_ms),
        data_used_mb=round((down.total + up.total) / 1e6, 1),
        started_at=started,
        downloaded_mb=round(down.total / 1e6, 1),
        uploaded_mb=round(up.total / 1e6, 1),
        download_ended_by=download.ended_by,
        upload_ended_by=upload.ended_by,
        download_s=round(download.seconds, 1),
        upload_s=round(upload.seconds, 1),
    )
