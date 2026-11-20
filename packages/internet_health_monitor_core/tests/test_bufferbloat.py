"""Bufferbloat: latency increase under load and its grade on Waveform's scale (REFERENCES.md § R3)."""

from __future__ import annotations

import pytest

from solentlabs.internet_health_monitor_core.bufferbloat import grade
from solentlabs.internet_health_monitor_core.speed_test import SpeedTestResult

# Increase in ms -> grade. Each bound belongs to the grade below it ("Less than 5 ms" is A+).
# ┌──────────┬───────┐
# │ ms       │ grade │
# ├──────────┼───────┤
# │ -2       │ A+    │
# │ 0 to 4.9 │ A+    │
# │ 5        │ A     │
# │ 29.9     │ A     │
# │ 30       │ B     │
# │ 59.9     │ B     │
# │ 60       │ C     │
# │ 199.9    │ C     │
# │ 200      │ D     │
# │ 399.9    │ D     │
# │ 400      │ F     │
# └──────────┴───────┘
# fmt: off
GRADE_CASES: list[tuple[float, str]] = [
    (-2.0,  "A+"), (0.0,   "A+"), (4.9,   "A+"),
    (5.0,   "A"),  (29.9,  "A"),
    (30.0,  "B"),  (59.9,  "B"),
    (60.0,  "C"),  (199.9, "C"),
    (200.0, "D"),  (399.9, "D"),
    (400.0, "F"),  (5000.0, "F"),
]
# fmt: on


@pytest.mark.parametrize("increase,expected", GRADE_CASES)
def test_grade(increase: float, expected: str) -> None:
    """Waveform's thresholds, each an upper bound."""
    assert grade(increase) == expected


# (idle, download loaded, upload loaded) -> (download increase, upload increase, grade).
# The worse direction decides the grade; a missing reading gives no grade.
# fmt: off
RESULT_CASES: list[tuple[str, tuple[float | None, ...], tuple[float | None, float | None, str | None]]] = [
    ("upload worse",     (12.0, 48.5, 310.0), (36.5, 298.0, "D")),
    ("download worse",   (12.0, 75.0, 20.0),  (63.0, 8.0,   "C")),
    ("both quiet",       (12.0, 13.0, 14.9),  (1.0,  2.9,   "A+")),
    ("no idle reading",  (None, 48.5, 310.0), (None, None,  None)),
    ("no upload reading", (12.0, 48.5, None), (36.5, None,  None)),
]
# fmt: on


@pytest.mark.parametrize("description,latencies,expected", RESULT_CASES, ids=[c[0] for c in RESULT_CASES])
def test_result_increases_and_grade(
    description: str, latencies: tuple[float | None, ...], expected: tuple[float | None, float | None, str | None]
) -> None:
    """Each direction's increase over idle; the grade is the worse one's, as Waveform grades."""
    idle, down, up = latencies
    result = SpeedTestResult("cloudflare", "s", 100.0, 10.0, idle, down, up, 1.0, 0.0)
    got = (result.download_latency_increase_ms, result.upload_latency_increase_ms, result.bufferbloat_grade)
    assert got == expected
    # The number the grade reads: the larger increase, only when both exist.
    larger = max(expected[0], expected[1]) if None not in expected[:2] else None  # type: ignore[type-var]
    assert result.bufferbloat_increase_ms == larger
    data = result.to_dict()
    assert (data["download_latency_increase_ms"], data["bufferbloat_grade"]) == (expected[0], expected[2])
    assert data["bufferbloat_increase_ms"] == larger
