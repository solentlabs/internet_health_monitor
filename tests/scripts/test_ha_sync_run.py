"""Tests for the dev start script's Home Assistant version check (ADR-008)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "ha-sync-run.py"
_spec = importlib.util.spec_from_file_location("ha_sync_run", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# (image version, minimum) -> supported?
# fmt: off
SUPPORT_CASES = [
    ("2026.10.0", "2026.10.0", True),
    ("2026.11.2", "2026.10.0", True),
    ("2026.9.3",  "2026.10.0", False),  # the local image that prompted this check
    ("2027.1.0",  "2026.10.0", True),
    (None,        "2026.10.0", False),  # image not pulled
]
# fmt: on


@pytest.mark.parametrize(("version", "minimum", "expected"), SUPPORT_CASES)
def test_is_supported(version: str | None, minimum: str, expected: bool) -> None:
    """Versions compare numerically, so 2026.10 is newer than 2026.9."""
    assert _mod.is_supported(version, minimum) is expected


@pytest.mark.parametrize(("text", "expected"), [("2026.10.4", (2026, 10, 4)), ("2026.10", (2026, 10, 0))])
def test_parse_version(text: str, expected: tuple[int, ...]) -> None:
    """A missing patch number counts as zero."""
    assert _mod.parse_version(text) == expected


def test_minimum_comes_from_hacs_json() -> None:
    """The script's minimum is the one hacs.json declares, not a copy."""
    hacs = json.loads((_SCRIPT.parents[2] / "hacs.json").read_text(encoding="utf-8"))
    assert _mod.minimum_ha_version() == hacs["homeassistant"]


def test_compose_image() -> None:
    """The image is read from docker-compose.test.yml."""
    assert _mod.compose_image() == "ghcr.io/home-assistant/home-assistant:stable"
