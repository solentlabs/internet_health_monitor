"""Tests that constants agree with the manifest."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.internet_health_monitor.const import DOMAIN, VERSION

MANIFEST = Path(__file__).resolve().parents[2] / "custom_components" / DOMAIN / "manifest.json"


def test_version_matches_manifest() -> None:
    """The version shown on the device equals the manifest version (single source drift check)."""
    assert json.loads(MANIFEST.read_text(encoding="utf-8"))["version"] == VERSION
