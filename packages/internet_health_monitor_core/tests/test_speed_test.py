"""Speed test backends against in-process fakes of each provider (loopback only, no real network)."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from solentlabs.internet_health_monitor_core import speed_test, timing
from solentlabs.internet_health_monitor_core.backends import _http, cloudflare
from solentlabs.internet_health_monitor_core.backends.cloudflare import CloudflareBackend
from solentlabs.internet_health_monitor_core.backends.librespeed import LibreSpeedBackend
from solentlabs.internet_health_monitor_core.backends.ndt7 import PROTOCOL, Ndt7Backend
from solentlabs.internet_health_monitor_core.speed_test import (
    USER_AGENT,
    SpeedTestBackend,
    SpeedTestError,
    SpeedTestResult,
    Transfer,
    run_speed_test,
)

pytestmark = pytest.mark.enable_socket  # loopback only: in-process servers on 127.0.0.1

LIMIT = 4_000_000  # bytes per direction: keeps every test fast
BLOCK = b"\0" * 65536
SLOW_BLOCK_S = 0.01

# A server answers a load or probe request with a redirect -> the test fails; the target gets nothing.
# A server answers with JSON of the wrong shape -> SpeedTestError, as every failure.
# fmt: off
MALFORMED_CASES: list[tuple[str, str, Any]] = [
    ("mlab",       "/locate",      ["not", "an", "object"]),
    ("mlab",       "/locate",      {"results": [{"urls": []}]}),
    ("librespeed", "/servers.php", {"not": "a list"}),
    ("librespeed", "/servers.php", [["not", "an", "object"]]),
]
# fmt: on

# fmt: off
REDIRECT_CASES: list[tuple[str, str]] = [
    ("cloudflare", "/__down"),               # download stream
    ("cloudflare", "/__up"),                 # upload stream
    ("librespeed", "/backend/garbage.php"),  # download stream
    ("librespeed", "/backend/empty.php"),    # probe and upload
]
# fmt: on


class Fake:
    """Every provider's endpoints on one loopback server; records what it was sent."""

    def __init__(self) -> None:
        self.user_agents: set[str] = set()
        self.paths: list[str] = []
        self.fail: set[str] = set()  # paths that answer 500
        self.malformed: dict[str, Any] = {}  # path -> JSON body of the wrong shape
        self.redirect: set[str] = set()  # paths that answer 302 to /elsewhere (a server pointing load at a LAN device)
        self.locate_status = 200
        self.slow = False  # load moves one block per SLOW_BLOCK_S each way: a line slower than the limit
        self.base = ""

    @web.middleware
    async def record(self, request: web.Request, handler: Callable[..., Any]) -> web.StreamResponse:
        """Note the path and User-Agent; fail paths in self.fail."""
        self.user_agents.add(request.headers.get("User-Agent", ""))
        self.paths.append(request.path)
        if request.path in self.fail:
            raise web.HTTPInternalServerError
        if request.path in self.redirect:
            raise web.HTTPFound("/elsewhere")
        if request.path in self.malformed:
            return web.json_response(self.malformed[request.path])
        result: web.StreamResponse = await handler(request)
        return result

    async def stream(self, request: web.Request, size: int) -> web.StreamResponse:
        """Send *size* bytes."""
        resp = web.StreamResponse(headers={"server-timing": "cfRequestDuration;dur=0.5"})
        await resp.prepare(request)
        sent = 0
        while sent < size:
            chunk = BLOCK[: min(len(BLOCK), size - sent)]
            await resp.write(chunk)
            sent += len(chunk)
            if self.slow and size > 0:
                await asyncio.sleep(SLOW_BLOCK_S)
        return resp

    async def cf_down(self, request: web.Request) -> web.StreamResponse:
        """Cloudflare __down?bytes=N."""
        return await self.stream(request, int(request.query["bytes"]))

    async def sink(self, request: web.Request) -> web.Response:
        """Accept an upload or a probe."""
        async for _ in request.content.iter_chunked(len(BLOCK)):
            if self.slow:
                await asyncio.sleep(SLOW_BLOCK_S)
        return web.Response(text="")

    async def libre_list(self, request: web.Request) -> web.Response:
        """LibreSpeed's server list: one dead server, one working one."""
        working = {"name": "Example", "server": f"{self.base}/backend", "dlURL": "garbage.php"}
        working |= {"ulURL": "empty.php", "pingURL": "empty.php"}
        dead = {**working, "name": "Dead", "server": "http://127.0.0.1:9/backend"}
        return web.json_response([dead, working, {"name": "Incomplete"}])

    async def libre_empty(self, request: web.Request) -> web.Response:
        """LibreSpeed empty.php behind nginx's default 1 MB body limit, as volunteer servers often are."""
        if len(await request.read()) > 1_048_576:
            raise web.HTTPRequestEntityTooLarge(max_size=1_048_576, actual_size=0)
        return web.Response(text="")

    async def garbage(self, request: web.Request) -> web.StreamResponse:
        """LibreSpeed garbage.php?ckSize=N: N MiB."""
        return await self.stream(request, int(request.query["ckSize"]) * 1048576)

    async def locate(self, request: web.Request) -> web.Response:
        """M-Lab Locate v2: a dead candidate first, then a working one."""
        assert request.query["client_name"] == "internet-health-monitor"
        if self.locate_status == 204:
            return web.Response(status=204)
        ws = self.base.replace("http", "ws")
        dead = {
            "machine": "dead",
            "urls": {"wss:///ndt/v7/download": "ws://127.0.0.1:9/x", "wss:///ndt/v7/upload": "x"},
        }
        live = {
            "machine": "mlab1-example",
            "location": {"city": "Example City"},
            "urls": {"wss:///ndt/v7/download": f"{ws}/ndt/v7/download", "wss:///ndt/v7/upload": f"{ws}/ndt/v7/upload"},
        }
        return web.json_response({"results": [dead, live]})

    async def ndt_download(self, request: web.Request) -> web.WebSocketResponse:
        """ndt7 download: binary messages with measurements, then close."""
        ws = web.WebSocketResponse(protocols=(PROTOCOL,))
        await ws.prepare(request)
        assert ws.ws_protocol == PROTOCOL
        for rtt in (20000, 30000, 40000):
            for _ in range(10):
                await ws.send_bytes(BLOCK)
            await ws.send_str(json.dumps({"TCPInfo": {"RTT": rtt, "MinRTT": 10000}}))
        await ws.send_str("not json")
        await ws.close()
        return ws

    async def ndt_upload(self, request: web.Request) -> web.WebSocketResponse:
        """ndt7 upload: count bytes and report them, as the server does."""
        ws = web.WebSocketResponse(protocols=(PROTOCOL,))
        await ws.prepare(request)
        received = 0
        async for msg in ws:
            if msg.type is aiohttp.WSMsgType.BINARY:
                received += len(msg.data)
                info = {"AppInfo": {"NumBytes": received, "ElapsedTime": 1_000_000}, "TCPInfo": {"RTT": 50000}}
                await ws.send_str(json.dumps(info))
        return ws

    def app(self) -> web.Application:
        """The aiohttp application."""
        app = web.Application(middlewares=[self.record], client_max_size=64 * 1024 * 1024)
        app.router.add_get("/__down", self.cf_down)
        app.router.add_post("/__up", self.sink)
        app.router.add_get("/servers.php", self.libre_list)
        app.router.add_get("/backend/garbage.php", self.garbage)
        app.router.add_route("*", "/backend/empty.php", self.libre_empty)
        app.router.add_get("/locate", self.locate)
        app.router.add_get("/ndt/v7/download", self.ndt_download)
        app.router.add_get("/ndt/v7/upload", self.ndt_upload)
        app.router.add_route("*", "/elsewhere", self.sink)
        return app


@pytest.fixture(autouse=True)
def limit_ends_each_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every run's order fixed, so results never depend on how busy the machine is.

    The data limit, never the clock, ends a direction: 4 MB moves on loopback in milliseconds,
    and the window is only a guard against a hung test. Each direction's load starts after a
    probe has answered, since on loopback the limit is otherwise reached before any probe returns.
    """
    monkeypatch.setattr(timing, "SPEED_TEST_DIRECTION_S", 30.0)
    monkeypatch.setattr(timing, "SPEED_TEST_WARMUP_S", 0.1)
    monkeypatch.setattr(timing, "SPEED_TEST_PROBE_INTERVAL_S", 0.02)
    answered = [0]
    original_probe = _http.probe

    async def counted_probe(session: aiohttp.ClientSession, server: _http.HttpServer) -> float:
        result = await original_probe(session, server)
        answered[0] += 1
        return result

    def after_a_probe(stream: _http.StreamFn) -> _http.StreamFn:
        async def gated(session: aiohttp.ClientSession, server: _http.HttpServer, index: int, counter: Any) -> None:
            seen = answered[0]
            while answered[0] == seen:
                await asyncio.sleep(0.001)
            await stream(session, server, index, counter)

        return gated

    monkeypatch.setattr(_http, "probe", counted_probe)
    monkeypatch.setattr(_http, "_download_stream", after_a_probe(_http._download_stream))
    monkeypatch.setattr(_http, "_upload_stream", after_a_probe(_http._upload_stream))


@pytest.fixture
async def fake() -> AsyncIterator[Fake]:
    """A running fake provider."""
    provider = Fake()
    server = TestServer(provider.app(), host="127.0.0.1")
    await server.start_server()
    provider.base = str(server.make_url("")).rstrip("/")
    yield provider
    await server.close()


@pytest.fixture
async def session() -> AsyncIterator[aiohttp.ClientSession]:
    """A client session, as a host would inject."""
    async with aiohttp.ClientSession() as client:
        yield client


BACKENDS: dict[str, Callable[[str], SpeedTestBackend]] = {
    "cloudflare": lambda base: CloudflareBackend(base),
    "librespeed": lambda base: LibreSpeedBackend(f"{base}/servers.php", require_tls=False),
    "mlab": lambda base: Ndt7Backend(f"{base}/locate", require_tls=False),
}

# ┌──────────────┬───────────────────────────────────────┬───────────────────┬─────────────────────────────────┐
# │ backend      │ server named                          │ latency fields    │ description                     │
# ├──────────────┼───────────────────────────────────────┼───────────────────┼─────────────────────────────────┤
# │ cloudflare   │ speed.cloudflare.com                  │ all three         │ server-timing subtracted        │
# │ librespeed   │ Example                               │ all three         │ dead and incomplete entries out │
# │ mlab         │ mlab1-example (Example City)          │ all three         │ dead candidate skipped          │
# └──────────────┴───────────────────────────────────────┴───────────────────┴─────────────────────────────────┘
# fmt: off
RUN_CASES: list[tuple[str, str]] = [
    ("cloudflare", "speed.cloudflare.com"),
    ("librespeed", "Example"),
    ("mlab",       "mlab1-example (Example City)"),
]
# fmt: on


@pytest.mark.parametrize("name,server", RUN_CASES, ids=[c[0] for c in RUN_CASES])
async def test_backend_measures_both_directions(
    fake: Fake, session: aiohttp.ClientSession, name: str, server: str
) -> None:
    """Each backend returns throughput both ways, every latency, data used, and identifies itself."""
    result = await BACKENDS[name](fake.base).run(session, LIMIT, Transfer())
    assert isinstance(result, SpeedTestResult)
    assert (result.backend, result.server) == (name, server)
    assert result.download_mbps > 0 and result.upload_mbps > 0
    assert None not in (result.idle_latency_ms, result.download_latency_ms, result.upload_latency_ms)
    assert result.data_used_mb == pytest.approx(result.downloaded_mb + result.uploaded_mb, abs=0.11)
    assert result.downloaded_mb > 0 and result.uploaded_mb > 0
    # Download stops at the limit; upload overshoots by what moves in one 50 ms check on loopback.
    assert 0 < result.data_used_mb <= 2 * LIMIT / 1e6 + 8
    assert fake.user_agents == {USER_AGENT}
    assert "/__results" not in fake.paths  # never reports to a results endpoint


async def test_time_ends_a_slow_line(
    fake: Fake, session: aiohttp.ClientSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a line too slow to reach the limit, each direction runs its full window; speed is timed after warm-up."""
    fake.slow = True
    window, warmup = 0.6, 0.2
    monkeypatch.setattr(timing, "SPEED_TEST_DIRECTION_S", window)
    monkeypatch.setattr(timing, "SPEED_TEST_WARMUP_S", warmup)
    measured: list[tuple[int, float]] = []
    original = _http._run_until

    async def recorded(tasks: list[asyncio.Task[None]], counter: Any, seconds: float) -> None:
        await original(tasks, counter, seconds)
        measured.append((counter.total, seconds))

    monkeypatch.setattr(_http, "_run_until", recorded)
    loop = asyncio.get_running_loop()
    start = loop.time()
    result = await CloudflareBackend(fake.base).run(session, 10**12, Transfer())
    assert loop.time() - start >= 2 * window  # time, not the limit, ended both directions
    assert result.download_mbps > 0 and result.upload_mbps > 0
    # Each direction: one wait for warm-up, one for the rest; throughput counts only the rest.
    (down_warm, _), (down_end, down_rest), (up_warm, _), (up_end, _) = measured
    assert down_rest == pytest.approx(window - warmup)
    assert 0 < down_warm < down_end and 0 < up_warm < up_end
    assert result.download_mbps <= (down_end - down_warm) * 8 / 1e6 / (window - warmup) * 1.01


async def test_ndt7_latency_and_upload_come_from_the_server(fake: Fake, session: aiohttp.ClientSession) -> None:
    """Idle is MinRTT, download latency the median RTT, upload throughput the server's byte count."""
    result = await Ndt7Backend(f"{fake.base}/locate", require_tls=False).run(session, LIMIT, Transfer())
    assert (result.idle_latency_ms, result.download_latency_ms, result.upload_latency_ms) == (10.0, 30.0, 50.0)


async def test_cloudflare_subtracts_server_time(fake: Fake, session: aiohttp.ClientSession) -> None:
    """A probe's time excludes the processing time Cloudflare reports."""
    server = _http.HttpServer(
        name="x",
        download_url=lambda _: "",
        upload_url=lambda: "",
        probe_url=lambda: f"{fake.base}/__down?bytes=0",
        server_time_ms=lambda _: 1e9,
    )
    assert await _http.probe(session, server) == 0.0


# ┌───────────────────────────────────────────────┬──────────────────────────────┐
# │ server-timing header                          │ ms subtracted                │
# ├───────────────────────────────────────────────┼──────────────────────────────┤
# │ cfRequestDuration;dur=12.5                    │ 12.5                         │
# │ cfReqDur;dur=3                                │ 3                            │
# │ cfSpeedA;dur=1, cfSpeedB;dur=2                │ 3 (summed)                   │
# │ (none)                                        │ 0                            │
# └───────────────────────────────────────────────┴──────────────────────────────┘
# fmt: off
SERVER_TIMING_CASES: list[tuple[str, float]] = [
    ("cfRequestDuration;dur=12.5",     12.5),
    ("cfReqDur;dur=3",                 3.0),
    ("cfSpeedA;dur=1, cfSpeedB;dur=2", 3.0),
    ("",                               0.0),
]
# fmt: on


@pytest.mark.parametrize("header,expected", SERVER_TIMING_CASES)
def test_cloudflare_server_time(header: str, expected: float) -> None:
    """Server time is read as Cloudflare's own client reads it."""

    class Resp:
        headers = {"server-timing": header} if header else {}

    assert cloudflare.server_time_ms(Resp()) == expected  # type: ignore[arg-type]  # rationale: only .headers is read


# ┌──────────────┬────────────────────────────────────────────┬──────────────────────────────────┐
# │ backend      │ fault                                      │ message mentions                 │
# ├──────────────┼────────────────────────────────────────────┼──────────────────────────────────┤
# │ mlab         │ Locate answers 204                         │ daily limit                      │
# │ librespeed   │ every server's probe fails                 │ no LibreSpeed server answered    │
# │ cloudflare   │ download endpoint fails                    │ ended early / 500                │
# └──────────────┴────────────────────────────────────────────┴──────────────────────────────────┘
def _locate_204(f: Fake) -> None:
    f.locate_status = 204


def _libre_dead(f: Fake) -> None:
    f.fail.add("/backend/empty.php")


def _cf_down_fails(f: Fake) -> None:
    f.fail.add("/__down")


# fmt: off
FAULT_CASES: list[tuple[str, Callable[[Fake], None], str]] = [
    ("mlab",       _locate_204,    "daily limit"),
    ("librespeed", _libre_dead,    "no LibreSpeed server answered"),
    ("cloudflare", _cf_down_fails, "500"),
]
# fmt: on


@pytest.mark.parametrize("name,fault,message", FAULT_CASES, ids=[c[2] for c in FAULT_CASES])
async def test_faults_raise_speed_test_error(
    fake: Fake, session: aiohttp.ClientSession, name: str, fault: Callable[[Fake], None], message: str
) -> None:
    """A provider fault never yields numbers: it raises SpeedTestError with the reason."""
    fault(fake)
    with pytest.raises((SpeedTestError, aiohttp.ClientResponseError)) as err:  # 500 surfaces as ClientResponseError
        await BACKENDS[name](fake.base).run(session, LIMIT, Transfer())
    assert message in str(err.value)


async def test_run_speed_test_wraps_errors_and_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_speed_test turns client errors and timeouts into SpeedTestError and halves the limit per direction."""
    seen: list[int] = []

    class Broken:
        name = "cloudflare"

        async def run(self, session: aiohttp.ClientSession, max_bytes: int, transfer: Transfer) -> SpeedTestResult:
            seen.append(max_bytes)
            raise aiohttp.ClientConnectionError("refused")

    class Slow:
        name = "cloudflare"

        async def run(self, session: aiohttp.ClientSession, max_bytes: int, transfer: Transfer) -> SpeedTestResult:
            await asyncio.sleep(10)
            raise AssertionError

    monkeypatch.setattr(speed_test, "_backends", lambda: {"cloudflare": Broken})
    with pytest.raises(SpeedTestError, match="refused"):
        await run_speed_test("cloudflare", None, data_limit_mb=500)  # type: ignore[arg-type]  # rationale: unused by the stub
    assert seen == [250_000_000]

    monkeypatch.setattr(speed_test, "_backends", lambda: {"cloudflare": Slow})
    monkeypatch.setattr(speed_test, "SPEED_TEST_TIMEOUT_S", 0.05)
    with pytest.raises(SpeedTestError, match="did not finish"):
        await run_speed_test("cloudflare", None)  # type: ignore[arg-type]  # rationale: unused by the stub


def test_every_backend_is_registered() -> None:
    """BACKEND_NAMES and the registry agree, and each backend reports its own name."""
    backends = speed_test._backends()
    assert tuple(backends) == speed_test.BACKEND_NAMES
    assert all(factory().name == name for name, factory in backends.items())


def test_result_to_dict() -> None:
    """Results are plain data."""
    result = SpeedTestResult("mlab", "s", 1.0, 2.0, None, None, None, 0.1, 0.0)
    assert result.to_dict()["backend"] == "mlab"


async def test_request_timeout_is_not_reported_as_test_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """A request's own timeout says so; only the whole-test limit reports the 60 s message."""

    class RequestTimesOut:
        name = "cloudflare"

        async def run(self, session: aiohttp.ClientSession, max_bytes: int, transfer: Transfer) -> SpeedTestResult:
            raise TimeoutError

    monkeypatch.setattr(speed_test, "_backends", lambda: {"cloudflare": RequestTimesOut})
    with pytest.raises(SpeedTestError, match="a request timed out"):
        await run_speed_test("cloudflare", None)  # type: ignore[arg-type]  # rationale: unused by the stub


def test_upload_streams_have_no_read_timeout() -> None:
    """A slow uplink takes longer than any read timeout to send one body; the direction's end stops it instead."""
    assert _http.UPLOAD_TIMEOUT.sock_read is None and _http.UPLOAD_TIMEOUT.total is None
    assert _http.UPLOAD_TIMEOUT.sock_connect == timing.SPEED_TEST_REQUEST_TIMEOUT_S


async def test_failed_test_reports_data_it_moved(
    fake: Fake, session: aiohttp.ClientSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A test that fails partway still reports the MB it moved, so usage totals match the ISP's count."""
    fake.fail.add("/__up")  # download completes, then every upload is refused after it is sent
    # Bodies smaller than the limit, so each stream waits for its refusal before the limit is reached.
    monkeypatch.setattr(_http, "UPLOAD_REQUEST_BYTES", _http.READ_CHUNK)
    monkeypatch.setattr(speed_test, "_backends", lambda: {"cloudflare": lambda: CloudflareBackend(fake.base)})
    with pytest.raises(SpeedTestError) as err:
        await run_speed_test("cloudflare", session, data_limit_mb=8)
    # Half the limit, plus the chunk each of the four streams had in flight when it was reached.
    assert 4.0 <= err.value.downloaded_mb <= 4.0 + 4 * 65536 / 1e6 + 0.05
    # The refused uploads were still sent onto the connection, so they count too, within the limit.
    assert 0 < err.value.uploaded_mb <= 4.0 + 4 * 65536 / 1e6 + 0.05


async def test_failure_before_connecting_moved_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A test that never connected reports zero data."""

    class Refused:
        name = "cloudflare"

        async def run(self, session: aiohttp.ClientSession, max_bytes: int, transfer: Transfer) -> SpeedTestResult:
            raise aiohttp.ClientConnectionError("refused")

    monkeypatch.setattr(speed_test, "_backends", lambda: {"cloudflare": Refused})
    with pytest.raises(SpeedTestError) as err:
        await run_speed_test("cloudflare", None)  # type: ignore[arg-type]  # rationale: unused by the stub
    assert (err.value.downloaded_mb, err.value.uploaded_mb) == (0.0, 0.0)


@pytest.mark.parametrize("name,path", REDIRECT_CASES, ids=[f"{c[0]} {c[1]}" for c in REDIRECT_CASES])
async def test_redirects_are_not_followed(
    fake: Fake, session: aiohttp.ClientSession, monkeypatch: pytest.MonkeyPatch, name: str, path: str
) -> None:
    """A redirect is refused, so a server cannot point the test's load at another address.

    Whether the run then fails depends on timing (an upload's window can close before any
    reply arrives); what must hold is that the redirect target gets nothing.
    """
    fake.redirect.add(path)
    monkeypatch.setattr(speed_test, "_backends", lambda: {name: lambda: BACKENDS[name](fake.base)})
    with contextlib.suppress(SpeedTestError):
        await run_speed_test(name, session, data_limit_mb=8)  # type: ignore[arg-type]
    assert fake.paths.count(path) >= 1  # the redirecting endpoint was used
    assert "/elsewhere" not in fake.paths


@pytest.mark.parametrize(
    "name,path,body", MALFORMED_CASES, ids=[f"{c[0]} {c[1]} {i}" for i, c in enumerate(MALFORMED_CASES)]
)
async def test_malformed_server_data_is_a_speed_test_error(
    fake: Fake, session: aiohttp.ClientSession, monkeypatch: pytest.MonkeyPatch, name: str, path: str, body: Any
) -> None:
    """Whatever shape a server's JSON takes, the test fails with SpeedTestError, never another exception."""
    fake.malformed[path] = body
    monkeypatch.setattr(speed_test, "_backends", lambda: {name: lambda: BACKENDS[name](fake.base)})
    with pytest.raises(SpeedTestError):
        await run_speed_test(name, session, data_limit_mb=8)  # type: ignore[arg-type]
