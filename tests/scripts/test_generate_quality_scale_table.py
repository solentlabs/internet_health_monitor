"""Tests for scripts/generate_quality_scale_table.py.

The freshness test keeps README.md's quality scale table in step with
quality_scale.yaml; the rest cover the counting and region replacement.
Ported from Cable Modem Monitor.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "generate_quality_scale_table.py"
_spec = importlib.util.spec_from_file_location("generate_quality_scale_table", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_ALL_RULES = [rule for rules in _mod.TIERS.values() for rule in rules]

# status of one Bronze rule -> expected Bronze row
# fmt: off
_STATUS_CASES = [
    ("done",   "| 20 / 20 | None |"),
    ("exempt", "| 20 / 20 | None |"),
    ("todo",   "| 19 / 20 | [`brands`]"),
]
# fmt: on


def test_readme_table_is_fresh() -> None:
    """The README region matches what quality_scale.yaml renders."""
    assert (
        _mod.README.read_text(encoding="utf-8") == _mod.render_readme()
    ), "run: python scripts/generate_quality_scale_table.py"


def test_yaml_grades_every_rule() -> None:
    """quality_scale.yaml grades exactly the rules in TIERS."""
    assert sorted(_mod.load_statuses()) == sorted(_ALL_RULES)


@pytest.mark.parametrize(("status", "expected"), _STATUS_CASES, ids=[c[0] for c in _STATUS_CASES])
def test_status_counting(status: str, expected: str) -> None:
    """done and exempt count as met; todo is listed as open."""
    statuses = dict.fromkeys(_ALL_RULES, "done")
    statuses["brands"] = status
    bronze_row = next(line for line in _mod.render_table(statuses).splitlines() if "Bronze" in line)
    assert expected in bronze_row


def test_rule_set_mismatch_fails() -> None:
    """A rule missing from the yaml stops the render."""
    statuses = dict.fromkeys(_ALL_RULES[1:], "done")
    with pytest.raises(SystemExit, match="missing"):
        _mod.render_table(statuses)


def test_missing_markers_fail() -> None:
    """A README without the generated region stops the render."""
    with pytest.raises(SystemExit, match="markers missing"):
        _mod.replace_region("no markers here", "body")
