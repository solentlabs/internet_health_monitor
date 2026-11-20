"""IHM's recent log records, kept in memory for the diagnostics download (ARCHITECTURE.md § Diagnostics).

HA OS keeps no log file a user can attach, and HA's system log holds only
warnings and errors, so without this a report would carry no history.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import override

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from solentlabs import internet_health_monitor_core

from .const import DOMAIN

# The integration's and Core's loggers; their child loggers propagate to these.
LOGGERS = (__name__.rpartition(".")[0], internet_health_monitor_core.__name__)
MAX_RECORDS = 200
DATA_LOG_BUFFER: HassKey[LogBuffer] = HassKey(f"{DOMAIN}_log_buffer")


class LogBuffer(logging.Handler):
    """The newest MAX_RECORDS records IHM's loggers emit, at whatever level HA's logger settings allow."""

    def __init__(self) -> None:
        """Start empty; the message keeps its traceback, if any."""
        super().__init__()
        self.setFormatter(logging.Formatter("%(message)s"))
        self._records: deque[dict[str, str]] = deque(maxlen=MAX_RECORDS)

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """Keep one record; a failure here never reaches the code that logged."""
        try:
            self._records.append(
                {
                    "time": dt_util.utc_from_timestamp(record.created).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": self.format(record),
                }
            )
        except Exception:  # noqa: BLE001  # rationale: logging.Handler's contract; handleError reports it
            self.handleError(record)

    def records(self) -> list[dict[str, str]]:
        """The kept records, oldest first."""
        return list(self._records)


def async_setup_log_buffer(hass: HomeAssistant) -> None:
    """Capture IHM's records from now on; one buffer per logger, replacing any from an earlier HA instance."""
    buffer = LogBuffer()
    for name in LOGGERS:
        logger = logging.getLogger(name)
        for old in [handler for handler in logger.handlers if isinstance(handler, LogBuffer)]:
            logger.removeHandler(old)
        logger.addHandler(buffer)
    hass.data[DATA_LOG_BUFFER] = buffer
