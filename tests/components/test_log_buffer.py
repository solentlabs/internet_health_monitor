"""Tests for the in-memory log buffer behind the diagnostics download."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from homeassistant.core import HomeAssistant

from custom_components.internet_health_monitor.log_buffer import (
    DATA_LOG_BUFFER,
    LOGGERS,
    MAX_RECORDS,
    LogBuffer,
    async_setup_log_buffer,
)

HA_LOGGER, CORE_LOGGER = LOGGERS

# Logger level (HA's logger settings) -> whether an INFO and a DEBUG record are kept.
# fmt: off
LEVEL_CASES: list[tuple[int, bool, bool]] = [
    (logging.DEBUG,   True,  True),   # debug logging on: everything
    (logging.INFO,    True,  False),  # HA's default
    (logging.WARNING, False, False),  # the user turned IHM down
]
# fmt: on


@pytest.fixture(autouse=True)
def restore_levels() -> Iterator[None]:
    """Put IHM's logger levels back after each test."""
    saved = {name: logging.getLogger(name).level for name in LOGGERS}
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)


def _buffer(hass: HomeAssistant) -> LogBuffer:
    """Set up the buffer, with both loggers at INFO as HA's default leaves them."""
    async_setup_log_buffer(hass)
    for name in LOGGERS:
        logging.getLogger(name).setLevel(logging.INFO)
    return hass.data[DATA_LOG_BUFFER]


async def test_captures_both_loggers_in_order(hass: HomeAssistant) -> None:
    """Records from the integration and from Core, oldest first, with level, logger and message."""
    buffer = _buffer(hass)
    logging.getLogger(f"{HA_LOGGER}.coordinator").info("Nightly speed test skipped: %s", "daily limit")
    logging.getLogger(f"{CORE_LOGGER}.network_diagnostics").warning("No hops detected")
    logging.getLogger("homeassistant.core").warning("not ours")
    records = buffer.records()
    assert [(r["level"], r["logger"], r["message"]) for r in records] == [
        ("INFO", f"{HA_LOGGER}.coordinator", "Nightly speed test skipped: daily limit"),
        ("WARNING", f"{CORE_LOGGER}.network_diagnostics", "No hops detected"),
    ]
    assert all(r["time"].endswith("+00:00") for r in records)


async def test_keeps_the_traceback(hass: HomeAssistant) -> None:
    """A record logged with an exception carries its traceback."""
    buffer = _buffer(hass)
    try:
        raise RuntimeError("card failed")
    except RuntimeError:
        logging.getLogger(HA_LOGGER).warning("Card not registered", exc_info=True)
    message = buffer.records()[-1]["message"]
    assert message.startswith("Card not registered\nTraceback")
    assert "RuntimeError: card failed" in message


async def test_a_bad_record_never_reaches_the_caller(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch) -> None:
    """A record that cannot be formatted is reported by logging and dropped; the code that logged runs on."""
    buffer = _buffer(hass)
    reported: list[logging.LogRecord] = []
    monkeypatch.setattr(buffer, "handleError", reported.append)
    record = logging.LogRecord(CORE_LOGGER, logging.INFO, __file__, 1, "%d hops", ("three",), None)
    buffer.emit(record)  # directly: pytest's own handler would re-raise the same error
    assert buffer.records() == [] and reported == [record]


async def test_keeps_only_the_newest(hass: HomeAssistant) -> None:
    """Past MAX_RECORDS the oldest records drop."""
    buffer = _buffer(hass)
    for n in range(MAX_RECORDS + 5):
        logging.getLogger(CORE_LOGGER).info("record %d", n)
    records = buffer.records()
    assert len(records) == MAX_RECORDS
    assert (records[0]["message"], records[-1]["message"]) == ("record 5", f"record {MAX_RECORDS + 4}")


@pytest.mark.parametrize("level,info_kept,debug_kept", LEVEL_CASES)
async def test_follows_ha_logger_settings(hass: HomeAssistant, level: int, info_kept: bool, debug_kept: bool) -> None:
    """The buffer keeps what the logger's level lets through; it never changes the level."""
    buffer = _buffer(hass)
    logging.getLogger(CORE_LOGGER).setLevel(level)
    logging.getLogger(CORE_LOGGER).info("info")
    logging.getLogger(CORE_LOGGER).debug("debug")
    expected = [m for m, kept in (("info", info_kept), ("debug", debug_kept)) if kept]
    assert [r["message"] for r in buffer.records()] == expected
    assert logging.getLogger(CORE_LOGGER).level == level


async def test_setup_again_replaces_the_buffer(hass: HomeAssistant) -> None:
    """A second setup in the same process leaves one buffer per logger, not two."""
    async_setup_log_buffer(hass)
    async_setup_log_buffer(hass)
    for name in LOGGERS:
        assert [h for h in logging.getLogger(name).handlers if isinstance(h, LogBuffer)] == [hass.data[DATA_LOG_BUFFER]]
