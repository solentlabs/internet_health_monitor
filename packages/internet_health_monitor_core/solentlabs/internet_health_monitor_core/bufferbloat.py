"""Bufferbloat graded on Waveform's published scale (docs/REFERENCES.md § R3).

The grade comes from one measured input, the larger latency increase under
load, read against a cited scale, so it is a reading, not a composite
(docs/ARCHITECTURE_DECISIONS.md § ADR-004).
"""

from __future__ import annotations

from typing import Literal

Grade = Literal["A+", "A", "B", "C", "D", "F"]

# Increase in ms below which each grade applies; WORST from the last bound up (R3).
SCALE: tuple[tuple[float, Grade], ...] = (
    (5.0, "A+"),
    (30.0, "A"),
    (60.0, "B"),
    (200.0, "C"),
    (400.0, "D"),
)


WORST: Grade = "F"


def grade(increase_ms: float) -> Grade:
    """Waveform's grade for a latency increase under load."""
    for bound, label in SCALE:
        if increase_ms < bound:
            return label
    return WORST
