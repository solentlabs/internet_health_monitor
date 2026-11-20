"""Check a release tag before anything is published, and give the release its notes.

release.yml runs it first (docs/RELEASING.md): the tag must be `v` and Core's version, manifest.json's
version and its Core pin must match it, CHANGELOG.md must have the version's heading, and, with `--on`,
the tagged commit must be in main's history. Pattern from leadline-metrics' tools/check_release.py.

    python scripts/check_release.py vX.Y.Z [--on origin/main]   # exit 0, or 1 naming each problem
    python scripts/check_release.py vX.Y.Z --notes              # the version's CHANGELOG section
    python scripts/check_release.py vX.Y.Z --prerelease         # true or false
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_PYPROJECT = "packages/internet_health_monitor_core/pyproject.toml"
MANIFEST = "custom_components/internet_health_monitor/manifest.json"
CORE_PACKAGE = "solentlabs-internet-health-monitor-core"


def problems(tag: str, root: Path = ROOT) -> list[str]:
    """What stops `tag` being released from `root`; empty when nothing does."""
    found = []
    version = tomllib.loads((root / CORE_PYPROJECT).read_text(encoding="utf-8"))["project"]["version"]
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    pins = [r.split("==", 1)[1] for r in manifest["requirements"] if r.startswith(f"{CORE_PACKAGE}==")]
    if tag != f"v{version}":
        found.append(f"tag {tag} does not match Core's version {version} ({CORE_PYPROJECT})")
    if manifest["version"] != version:
        found.append(f"manifest.json version {manifest['version']} does not match Core's version {version}")
    if pins != [version]:
        found.append(f"manifest.json pins Core {', '.join(pins) or 'nothing'}, not {version}")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.MULTILINE):
        found.append(f"CHANGELOG.md has no heading `## [{version}] - YYYY-MM-DD`")
    return found


def notes(version: str, root: Path = ROOT) -> str:
    """The version's CHANGELOG section, without its heading."""
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def is_prerelease(version: str) -> bool:
    """Whether a PEP 440 version is an alpha, beta or release candidate."""
    return re.search(r"[a-z]", version) is not None


def not_on(branch: str, root: Path = ROOT) -> list[str]:
    """What stops the checked-out commit being released: it is not in `branch`'s history."""
    # git from the PATH, with the branch the workflow names; nothing from the tag's contents.
    done = subprocess.run(  # noqa: S603
        ["git", "merge-base", "--is-ancestor", "HEAD", branch],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode == 0:
        return []
    if done.returncode == 1:
        return [f"the tagged commit is not on {branch}: merge it there first"]
    return [f"cannot compare the tagged commit with {branch}: {done.stderr.strip()}"]


def main(argv: list[str], root: Path = ROOT) -> int:
    """Run the check, or print the notes or the pre-release flag."""
    tag = argv[0]
    if "--notes" in argv:
        print(notes(tag.removeprefix("v"), root))
        return 0
    if "--prerelease" in argv:
        print(str(is_prerelease(tag.removeprefix("v"))).lower())
        return 0
    found = problems(tag, root)
    if "--on" in argv:
        found += not_on(argv[argv.index("--on") + 1], root)
    for problem in found:
        sys.stderr.write(f"{problem}\n")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
