"""Measure what IHM adds to Home Assistant's SQLite database, using HA's own recorder schema.

Two figures for users (.github/README.md § Database Space, REFERENCES.md § R28):

- State history: every change of an IHM sensor, kept 10 days by default, then purged.
  Always recorded; an integration cannot turn it off (R23).
- Long-term statistics: hourly mean, min and max per measurement sensor, never purged,
  plus 5-minute rows kept 10 days. Only with the Long-term statistics option on (ADR-013).

Run from the repository root: .venv/bin/python -I scripts/dev/measure_recorder_size.py
It writes a throwaway database in a temporary directory; nothing touches the network.
"""

from __future__ import annotations

import os
import random
import sqlite3
import tempfile
import time
from collections.abc import Iterator
from typing import Any

from homeassistant.components.recorder.db_schema import (
    SCHEMA_VERSION,
    Base,
    StateAttributes,
    States,
    StatesMeta,
    Statistics,
    StatisticsMeta,
    StatisticsShortTerm,
)
from sqlalchemy import Engine, create_engine, insert

DAYS_KEPT = 10  # recorder purge_keep_days default (R23)
POLLS_PER_DAY = 24 * 60  # one poll a minute (ADR-007)
HOURS_PER_YEAR = 24 * 365
# Measurement sensors that change almost every poll, with the default options: hop 1 to 3
# latency and jitter, internet reference latency and jitter, DNS latency.
CHANGING_DEFAULT = 9
# Usage totals on adds two counters that change every poll: pings and DNS queries.
CHANGING_USAGE = 2
# Measurement sensors with long-term statistics on: 9 hop, 1 DNS, 3 internet reference,
# 6 speed test readings (13 without a speed test service).
STATISTICS_SENSORS = 19
STATISTICS_SENSORS_NO_SPEED_TEST = 13
MB = 1e6


def vacuumed_size(path: str) -> int:
    """File size after VACUUM, so free pages are not counted."""
    con = sqlite3.connect(path)
    con.execute("VACUUM")
    con.close()
    return os.path.getsize(path)


def fresh(path: str) -> Engine:
    """An empty database with HA's recorder tables and indexes."""
    if os.path.exists(path):
        os.remove(path)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return engine


def state_rows(meta_ids: list[int], polls: int, start: float) -> Iterator[dict[str, Any]]:
    """One row per change, as HA writes it: last_changed and last_reported left null when equal."""
    previous: dict[int, int] = {}
    state_id = 0
    for poll in range(polls):
        for metadata_id in meta_ids:
            state_id += 1
            yield {
                "state_id": state_id,
                "state": f"{random.uniform(0.5, 60.0):.3f}",
                "last_updated_ts": start + poll * 60 + metadata_id * 0.001,
                "old_state_id": previous.get(metadata_id),
                "attributes_id": metadata_id,
                "origin_idx": 0,
                "context_id_bin": os.urandom(16),
                "metadata_id": metadata_id,
            }
            previous[metadata_id] = state_id


def state_history_mb(path: str, sensors: int) -> float:
    """Size of 10 days of one-minute changes for *sensors*: the level state history holds at."""
    engine = fresh(path)
    meta_ids = list(range(1, sensors + 1))
    with engine.begin() as con:
        con.execute(
            insert(StatesMeta), [{"metadata_id": m, "entity_id": f"sensor.internet_health_s{m}"} for m in meta_ids]
        )
        attrs = '{"hop_ip":"192.168.1.1","reachable":true,"address_type":"private","packets_sent":3}'
        con.execute(insert(StateAttributes), [{"attributes_id": m, "hash": m, "shared_attrs": attrs} for m in meta_ids])
    empty = vacuumed_size(path)
    with engine.begin() as con:
        con.execute(insert(States), list(state_rows(meta_ids, DAYS_KEPT * POLLS_PER_DAY, 1.7e9)))
    return (vacuumed_size(path) - empty) / MB


def statistic_rows(meta_ids: list[int], count: int, step_s: int, start: float) -> Iterator[dict[str, Any]]:
    """Mean, min and max per period, as HA compiles for a measurement sensor."""
    now = time.time()
    for metadata_id in meta_ids:
        for i in range(count):
            mean = random.uniform(0.5, 60.0)
            yield {
                "metadata_id": metadata_id,
                "created_ts": now,
                "start_ts": start + i * step_s,
                "mean": round(mean, 6),
                "min": round(mean * 0.8, 6),
                "max": round(mean * 1.4, 6),
            }


def statistics_mb(path: str, sensors: int) -> tuple[float, float]:
    """(5-minute rows for 10 days, held level; hourly rows per year, never purged) for *sensors*."""
    engine = fresh(path)
    meta_ids = list(range(1, sensors + 1))
    with engine.begin() as con:
        con.execute(
            insert(StatisticsMeta),
            [
                {
                    "statistic_id": f"sensor.internet_health_s{m}",
                    "source": "recorder",
                    "has_mean": True,
                    "has_sum": False,
                }
                for m in meta_ids
            ],
        )
    empty = vacuumed_size(path)
    with engine.begin() as con:
        rows = DAYS_KEPT * POLLS_PER_DAY // 5
        con.execute(insert(StatisticsShortTerm), list(statistic_rows(meta_ids, rows, 300, 1.7e9)))
    short = vacuumed_size(path)
    with engine.begin() as con:
        con.execute(insert(Statistics), list(statistic_rows(meta_ids, HOURS_PER_YEAR, 3600, 1.7e9)))
    return (short - empty) / MB, (vacuumed_size(path) - short) / MB


def main() -> None:
    """Print each figure."""
    random.seed(0)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "recorder.db")
        print(f"HA recorder schema {SCHEMA_VERSION}, SQLite")
        print("State history, 10 days, held level (always recorded):")
        print(f"  default options: {state_history_mb(path, CHANGING_DEFAULT):.1f} MB")
        print(f"  with usage totals: {state_history_mb(path, CHANGING_DEFAULT + CHANGING_USAGE):.1f} MB")
        print("Long-term statistics (option on): 5-minute rows held level; hourly rows per year, never purged:")
        for label, sensors in (
            ("with a speed test service", STATISTICS_SENSORS),
            ("without", STATISTICS_SENSORS_NO_SPEED_TEST),
        ):
            short, year = statistics_mb(path, sensors)
            print(f"  {label}: {short:.1f} MB held, {year:.1f} MB per year")


if __name__ == "__main__":
    main()
