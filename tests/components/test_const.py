"""Tests that constants agree with the manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.internet_health_monitor.const import DOMAIN, VERSION

MANIFEST = Path(__file__).resolve().parents[2] / "custom_components" / DOMAIN / "manifest.json"


def test_version_matches_manifest() -> None:
    """The version shown on the device equals the manifest version (single source drift check)."""
    assert json.loads(MANIFEST.read_text(encoding="utf-8"))["version"] == VERSION


ROOT = MANIFEST.parents[2]


def test_minimum_ha_agrees() -> None:
    """hacs.json, requirements-dev.txt and ha-minimum.txt state the same HA floor (ADR-008)."""
    import re

    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))["homeassistant"]
    floors = {
        name: re.search(r"^homeassistant>=([\d.]+)", (ROOT / name).read_text(encoding="utf-8"), re.M)
        for name in ("requirements-dev.txt", "ha-minimum.txt")
    }
    assert {name: m.group(1) if m else None for name, m in floors.items()} == {
        "requirements-dev.txt": hacs,
        "ha-minimum.txt": hacs,
    }


TRANSLATIONS = MANIFEST.parent / "translations"


def _keys(tree: object, prefix: str = "") -> set[str]:
    """Every leaf key path in a strings tree."""
    if not isinstance(tree, dict):
        return {prefix}
    return {path for key, value in tree.items() for path in _keys(value, f"{prefix}.{key}" if prefix else key)}


@pytest.mark.parametrize("language", sorted(p.stem for p in TRANSLATIONS.glob("*.json")))
def test_translation_has_every_string(language: str) -> None:
    """Each translation has exactly strings.json's keys: none missing, none left over."""
    source = _keys(json.loads((MANIFEST.parent / "strings.json").read_text(encoding="utf-8")))
    translated = _keys(json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")))
    assert (sorted(source - translated), sorted(translated - source)) == ([], [])
