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

from .bufferbloat import Grade, grade
from .timing import SPEED_TEST_DATA_LIMIT_MB_DEFAULT, SPEED_TEST_TIMEOUT_S

BackendName = Literal["cloudflare", "mlab", "librespeed"]
# What stopped a direction: its time window (or, for M-Lab's download, the server), or its data limit.
EndedBy = Literal["time", "data_limit"]

try:
    _VERSION = version("solentlabs-internet-health-monitor-core")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install metadata
    _VERSION = "0"

CLIENT_NAME = "internet-health-monitor"
CLIENT_VERSION = _VERSION
# Honest identification (ADR-003): every request a backend sends carries this.
USER_AGENT = f"{CLIENT_NAME}/{CLIENT_VERSION} (+https://github.com/solentlabs/internet_health_monitor)"


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
class DataLimit:
    """MB each direction may use; a direction stops when it reaches its own."""

    download_mb: int
    upload_mb: int

    @classmethod
    def even(cls, total_mb: int) -> DataLimit:
        """A limit for the whole test, split evenly between the directions."""
        return cls(total_mb // 2, total_mb - total_mb // 2)

    @property
    def total_mb(self) -> int:
        """Both directions together: the most the test may use."""
        return self.download_mb + self.upload_mb


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
    # How each direction ended, and how long it was loaded, in seconds: whether the test was whole.
    download_ended_by: EndedBy | None = None
    upload_ended_by: EndedBy | None = None
    download_s: float | None = None
    upload_s: float | None = None

    @property
    def download_latency_increase_ms(self) -> float | None:
        """Loaded minus idle latency while downloading: bufferbloat in that direction."""
        return _increase(self.download_latency_ms, self.idle_latency_ms)

    @property
    def upload_latency_increase_ms(self) -> float | None:
        """Loaded minus idle latency while uploading: bufferbloat in that direction."""
        return _increase(self.upload_latency_ms, self.idle_latency_ms)

    @property
    def bufferbloat_increase_ms(self) -> float | None:
        """The larger of the two increases, which the grade reads; None without both."""
        down, up = self.download_latency_increase_ms, self.upload_latency_increase_ms
        return max(down, up) if down is not None and up is not None else None

    @property
    def bufferbloat_grade(self) -> Grade | None:
        """Waveform's grade of the larger increase (bufferbloat.py); None without both."""
        increase = self.bufferbloat_increase_ms
        return grade(increase) if increase is not None else None

    def to_dict(self) -> dict[str, Any]:
        """Plain data for JSON output and diagnostics, with the increases and grade."""
        return {
            **asdict(self),
            "download_latency_increase_ms": self.download_latency_increase_ms,
            "upload_latency_increase_ms": self.upload_latency_increase_ms,
            "bufferbloat_increase_ms": self.bufferbloat_increase_ms,
            "bufferbloat_grade": self.bufferbloat_grade,
        }


def _increase(loaded_ms: float | None, idle_ms: float | None) -> float | None:
    """Loaded minus idle, to 0.1 ms; None if either is missing. Noise can make it slightly negative."""
    return round(loaded_ms - idle_ms, 1) if loaded_ms is not None and idle_ms is not None else None


class SpeedTestBackend(Protocol):
    """One provider. `run` measures both directions or raises SpeedTestError."""

    @property
    def name(self) -> BackendName:
        """The backend's key in BACKEND_NAMES."""
        ...

    async def run(self, session: aiohttp.ClientSession, limit: DataLimit, transfer: Transfer) -> SpeedTestResult:
        """Run one test; each direction stops at its *limit*; add every byte moved to *transfer* as it moves."""
        ...


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
    backend: BackendName,
    session: aiohttp.ClientSession,
    data_limit: DataLimit = DataLimit.even(SPEED_TEST_DATA_LIMIT_MB_DEFAULT),  # noqa: B008  # frozen, so shared safely
) -> SpeedTestResult:
    """Run one test with *backend* within *data_limit*; any failure, timeout included, raises SpeedTestError."""
    runner = _backends()[backend]()
    transfer = Transfer()
    limit = asyncio.timeout(SPEED_TEST_TIMEOUT_S)
    try:
        async with limit:
            return await runner.run(session, data_limit, transfer)
    except SpeedTestError as err:
        message = str(err)
        cause: BaseException = err
    except TimeoutError as err:
        if limit.expired():
            message = f"{backend} test did not finish within {SPEED_TEST_TIMEOUT_S:.0f} s"
        else:
            message = f"{backend} test failed: a request timed out"
        cause = err
    # ValueError to IndexError: a server's JSON of an unexpected shape, which nothing can trust.
    except (aiohttp.ClientError, OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as err:
        message, cause = f"{backend} test failed: {err or type(err).__name__}", err
    # Every failure leaves here, carrying the data the test moved before it failed.
    downloaded_mb, uploaded_mb = transfer.mb()
    raise SpeedTestError(message, downloaded_mb, uploaded_mb) from cause


def now() -> float:
    """Wall-clock start time for results (seconds since the epoch)."""
    return time.time()
