"""Every download carries the MIT notice, the license's one condition: the PyPI wheel and the HACS zip."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "packages" / "internet_health_monitor_core"


def test_core_license_matches_the_repository() -> None:
    """Core's copy, which hatchling puts in the wheel, is the repository's LICENSE word for word."""
    assert (CORE / "LICENSE").read_text(encoding="utf-8") == (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_hacs_zip_includes_the_license() -> None:
    """release.yml adds LICENSE to the integration zip it publishes."""
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert 'zip -j "$GITHUB_WORKSPACE/internet_health_monitor.zip" "$GITHUB_WORKSPACE/LICENSE"' in workflow
