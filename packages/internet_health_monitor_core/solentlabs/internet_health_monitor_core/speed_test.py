"""Speed tests: one interface, one result, one module per backend (ADR-003).

Hosts call `run_speed_test(backend, session)`. Each backend lives in
`backends/` and implements `SpeedTestBackend`; adding one means adding its
module and an entry in `BACKENDS` (docs/SPEED_TEST_BACKENDS.md § Adding a Backend).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Literal, Protocol

import aiohttp

from .timing import SPEED_TEST_DATA_LIMIT_MB_DEFAULT, SPEED_TEST_TIMEOUT_S

BackendName = Literal["cloudflare", "mlab", "librespeed"]

try:
    _VERSION = version("solentlabs-internet-health-monitor-core")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install metadata
    _VERSION = "0"

CLIENT_NAME = "internet-health-monitor"
CLIENT_VERSION = _VERSION
# Honest identification (ADR-003): every request a backend sends carries this.
USER_AGENT = f"{CLIENT_NAME}/{CLIENT_VERSION} (+https://github.com/solentlabs/internet-health-monitor)"


class SpeedTestError(Exception):
    """A speed test could not produce a result; the message says why.

    It still reports the data it moved before failing, which counts against a data cap.
    """

    def __init__(self, message: str, downloaded_mb: float = 0.0, uploaded_mb: float = 0.0) -> None:
        """Record the reason and the MB received and sent before the failure."""
        super().__init__(message)
        self.downloaded_mb = downloaded_mb
        self.uploaded_mb = uploaded_mb


@dataclass
class Transfer:
    """Bytes a test has moved so far: received, and handed to the network to send."""

    downloaded: int = 0
    uploaded: int = 0

    def mb(self) -> tuple[float, float]:
        """(downloaded, uploaded) in MB, to 0.1."""
        return round(self.downloaded / 1e6, 1), round(self.uploaded / 1e6, 1)


@dataclass(frozen=True)
class SpeedTestResult:
    """One completed test. Latencies are medians in ms; None where the backend has no reading."""

    backend: BackendName
    server: str
    download_mbps: float
    upload_mbps: float
    idle_latency_ms: float | None
    download_latency_ms: float | None
    upload_latency_ms: float | None
    data_used_mb: float
    started_at: float
    downloaded_mb: float = 0.0  # the two parts of data_used_mb
    uploaded_mb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Plain data for JSON output and diagnostics."""
        return asdict(self)


class SpeedTestBackend(Protocol):
    """One provider. `run` measures both directions or raises SpeedTestError."""

    @property
    def name(self) -> BackendName:
        """The backend's key in BACKEND_NAMES."""

    async def run(self, session: aiohttp.ClientSession, max_bytes: int, transfer: Transfer) -> SpeedTestResult:
        """Run one test; each direction stops at *max_bytes*; add every byte moved to *transfer* as it moves."""


def _backends() -> dict[BackendName, Callable[[], SpeedTestBackend]]:
    """Name -> factory; imported lazily so one backend's import cost is not every host's."""
    from .backends.cloudflare import CloudflareBackend
    from .backends.librespeed import LibreSpeedBackend
    from .backends.ndt7 import Ndt7Backend

    backends: dict[BackendName, Callable[[], SpeedTestBackend]] = {
        "cloudflare": CloudflareBackend,
        "mlab": Ndt7Backend,
        "librespeed": LibreSpeedBackend,
    }
    return backends


BACKEND_NAMES: tuple[BackendName, ...] = ("cloudflare", "mlab", "librespeed")


async def run_speed_test(
    backend: BackendName, session: aiohttp.ClientSession, data_limit_mb: int = SPEED_TEST_DATA_LIMIT_MB_DEFAULT
) -> SpeedTestResult:
    """Run one test with *backend* within *data_limit_mb*; any failure, timeout included, raises SpeedTestError."""
    runner = _backends()[backend]()
    transfer = Transfer()
    limit = asyncio.timeout(SPEED_TEST_TIMEOUT_S)
    try:
        async with limit:
            return await runner.run(session, data_limit_mb * 1_000_000 // 2, transfer)
    except SpeedTestError as err:
        message = str(err)
        cause: BaseException = err
    except TimeoutError as err:
        if limit.expired():
            message = f"{backend} test did not finish within {SPEED_TEST_TIMEOUT_S:.0f} s"
        else:
            message = f"{backend} test failed: a request timed out"
        cause = err
    except (aiohttp.ClientError, OSError, ValueError, KeyError) as err:
        message, cause = f"{backend} test failed: {err or type(err).__name__}", err
    # Every failure leaves here, carrying the data the test moved before it failed.
    downloaded_mb, uploaded_mb = transfer.mb()
    raise SpeedTestError(message, downloaded_mb, uploaded_mb) from cause


def now() -> float:
    """Wall-clock start time for results (seconds since the epoch)."""
    return time.time()
