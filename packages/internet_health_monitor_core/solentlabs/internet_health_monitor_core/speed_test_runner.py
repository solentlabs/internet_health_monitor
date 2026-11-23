"""Run a speed test with a named backend: the registry and the one entry point hosts call (ADR-003).

Adding a backend means adding its module in `backends/`, its name to
`speed_test.BACKEND_NAMES`, and an entry in `_backends` here
(docs/SPEED_TEST_BACKENDS.md § Adding a Backend).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import aiohttp

from .speed_test import BackendName, DataLimit, SpeedTestBackend, SpeedTestError, SpeedTestResult, Transfer
from .timing import SPEED_TEST_DATA_LIMIT_MB_DEFAULT, SPEED_TEST_TIMEOUT_S


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
