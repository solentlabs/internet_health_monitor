"""Tests for scripts/check_release.py: what stops a tag being released, and the notes it carries."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_release.py"
_spec = importlib.util.spec_from_file_location("check_release", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

CHANGELOG = """# Changelog

## [Unreleased]

## [0.2.0] - 2026-12-01

### Added

- Something new.

## [0.1.0] - 2026-11-30

- First release.
"""

# (Core version, manifest version, manifest pin, tag) -> problems named (substrings), in order
# fmt: off
PROBLEM_CASES: list[tuple[str, tuple[str, str, str, str], list[str]]] = [
    ("all agree",                ("0.2.0", "0.2.0", "0.2.0", "v0.2.0"), []),
    ("tag differs",              ("0.2.0", "0.2.0", "0.2.0", "v0.2.1"), ["tag v0.2.1"]),
    ("manifest version behind",  ("0.2.0", "0.1.0", "0.2.0", "v0.2.0"), ["manifest.json version 0.1.0"]),
    ("manifest pins old Core",   ("0.2.0", "0.2.0", "0.1.0", "v0.2.0"), ["pins Core 0.1.0"]),
    ("no CHANGELOG heading",     ("0.3.0", "0.3.0", "0.3.0", "v0.3.0"), ["CHANGELOG.md has no heading `## [0.3.0]"]),
    ("tag without v",            ("0.2.0", "0.2.0", "0.2.0", "0.2.0"),  ["tag 0.2.0"]),
]
# fmt: on

# Core version -> whether GitHub marks the release a pre-release (PEP 440: any letter means one)
# fmt: off
PRERELEASE_CASES: list[tuple[str, bool]] = [
    ("0.2.0",     False),
    ("0.2.0b3",   True),
    ("1.0.0rc1",  True),
    ("1.0.0a1",   True),
]
# fmt: on


def _repo(tmp_path: Path, core: str, manifest: str, pin: str) -> Path:
    """A tree with the four files the check reads."""
    package = tmp_path / "packages" / "internet_health_monitor_core"
    package.mkdir(parents=True)
    (package / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "{core}"\n')
    integration = tmp_path / "custom_components" / "internet_health_monitor"
    integration.mkdir(parents=True)
    manifest_data = {"version": manifest, "requirements": [f"solentlabs-internet-health-monitor-core=={pin}"]}
    (integration / "manifest.json").write_text(json.dumps(manifest_data))
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG)
    return tmp_path


@pytest.mark.parametrize("description,versions,expected", PROBLEM_CASES, ids=[c[0] for c in PROBLEM_CASES])
def test_problems(tmp_path: Path, description: str, versions: tuple[str, str, str, str], expected: list[str]) -> None:
    """The tag, Core's version, the manifest's version and its Core pin agree, and the CHANGELOG names the version."""
    core, manifest, pin, tag = versions
    found = _mod.problems(tag, _repo(tmp_path, core, manifest, pin))
    assert len(found) == len(expected)
    assert all(want in got for want, got in zip(expected, found, strict=True))


def test_notes_are_the_version_section(tmp_path: Path) -> None:
    """Release notes are the version's CHANGELOG section, without its heading or the next version's."""
    root = _repo(tmp_path, "0.2.0", "0.2.0", "0.2.0")
    assert _mod.notes("0.2.0", root) == "### Added\n\n- Something new."
    assert _mod.notes("0.1.0", root) == "- First release."


@pytest.mark.parametrize("version,expected", PRERELEASE_CASES)
def test_prerelease(version: str, expected: bool) -> None:
    """Alpha, beta and release-candidate versions become GitHub pre-releases."""
    assert _mod.is_prerelease(version) is expected


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_tagged_commit_must_be_on_main(tmp_path: Path) -> None:
    """A commit that never reached main publishes nothing."""
    root = _repo(tmp_path, "0.2.0", "0.2.0", "0.2.0")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "-c", "user.email=dev@example.com", "-c", "user.name=dev", "commit", "-q", "--allow-empty", "-m", "a")
    assert _mod.not_on("main", root) == []
    _git(root, "checkout", "-q", "-b", "side")
    _git(root, "-c", "user.email=dev@example.com", "-c", "user.name=dev", "commit", "-q", "--allow-empty", "-m", "b")
    assert "not on main" in _mod.not_on("main", root)[0]
    assert "cannot compare" in _mod.not_on("no-such-branch", root)[0]


def test_main_reports_and_prints(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Exit 1 naming each problem; with --notes, exit 0 printing the notes; --prerelease prints true or false."""
    root = _repo(tmp_path, "0.2.0", "0.2.0", "0.1.0")
    assert _mod.main(["v0.2.0"], root) == 1
    assert "pins Core 0.1.0" in capsys.readouterr().err
    assert _mod.main(["v0.2.0", "--notes"], root) == 0
    assert capsys.readouterr().out.strip() == "### Added\n\n- Something new."
    assert _mod.main(["v0.2.0b1", "--prerelease"], root) == 0
    assert capsys.readouterr().out.strip() == "true"
