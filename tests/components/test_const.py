"""Tests that constants agree with the manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.internet_health_monitor.const import DOMAIN, VERSION

MANIFEST = Path(__file__).resolve().parents[2] / "custom_components" / DOMAIN / "manifest.json"

# Strings that are genuinely the same in another language: grades, names, addresses, loanwords.
_ALLOW_IDENTICAL = frozenset(
    {
        *("A+", "A", "B", "C", "D", "F"),
        "Cloudflare",
        "Cloudflare (1.1.1.1)",
        "Google (8.8.8.8)",
        "OpenDNS (208.67.222.222)",
        "Quad9 (9.9.9.9)",
        "Internet Health Monitor",
        "Home Assistant OS",
        "Core",
        "Supervised",
        "Backend",
        "Bridge",
        "Container",
        "Ethernet",
        "Interface",
        "Server",
        "Wi-Fi",
        "pings",
        "tests",
        "traceroutes",
    }
)


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


def _leaves(tree: object, prefix: str = "") -> dict[str, object]:
    """Every leaf key path in a strings tree, with its value."""
    if not isinstance(tree, dict):
        return {prefix: tree}
    return {
        path: value
        for key, child in tree.items()
        for path, value in _leaves(child, f"{prefix}.{key}" if prefix else key).items()
    }


@pytest.mark.parametrize("language", sorted(p.stem for p in TRANSLATIONS.glob("*.json")))
def test_translation_has_every_string(language: str) -> None:
    """Each translation has exactly strings.json's keys: none missing, none left over."""
    source = set(_leaves(json.loads((MANIFEST.parent / "strings.json").read_text(encoding="utf-8"))))
    translated = set(_leaves(json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))))
    assert (sorted(source - translated), sorted(translated - source)) == ([], [])


@pytest.mark.parametrize("language", sorted(p.stem for p in TRANSLATIONS.glob("*.json") if p.stem != "en"))
def test_translation_is_translated(language: str) -> None:
    """No translated value equals the English unless it is genuinely the same in every language."""
    source = _leaves(json.loads((MANIFEST.parent / "strings.json").read_text(encoding="utf-8")))
    translated = _leaves(json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")))
    untranslated = {
        path: value for path, value in translated.items() if value == source.get(path) and value not in _ALLOW_IDENTICAL
    }
    assert untranslated == {}


def test_every_sensor_has_an_icon() -> None:
    """Each sensor in strings.json has an icon in icons.json, so none falls back to a default."""
    strings = json.loads((MANIFEST.parent / "strings.json").read_text(encoding="utf-8"))
    icons = json.loads((MANIFEST.parent / "icons.json").read_text(encoding="utf-8"))
    assert sorted(set(strings["entity"]["sensor"]) - set(icons["entity"]["sensor"])) == []
