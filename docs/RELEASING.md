# Releasing

How a version reaches PyPI, GitHub and HACS. One workflow does it all:
`.github/workflows/release.yml`, on the pattern of leadline-metrics'
release and PyPA's publishing guide.

## What a Release Is

- **Core** on PyPI: `solentlabs-internet-health-monitor-core`, the
  version `manifest.json` pins (ADR-005).
- **The integration** as a GitHub release with
  `internet_health_monitor.zip`, which HACS installs (`hacs.json`:
  `zip_release`, `filename`; `hide_default_branch` keeps users on
  releases).

## Versions

One version, in four places that must agree:

- Core's `packages/internet_health_monitor_core/pyproject.toml`
- `manifest.json` `version`, and its pin of Core
- `const.py` `VERSION` (`tests/components/test_const.py` checks it
  against the manifest)

CHANGELOG.md has a heading `## [X.Y.Z] - YYYY-MM-DD` for it. A version
with a letter (`0.2.0b1`, PEP 440) becomes a GitHub pre-release.

## To Release

1. In one commit on `main`: set the version in the four places and
   rename CHANGELOG.md's `## [Unreleased]` to the version's heading.
2. Push a tag `v` and the version:

   ```bash
   git tag v0.1.0 && git push origin v0.1.0
   ```

The workflow then runs, each step only if the one before passed:

1. **CI**: `tests.yml` on the tagged commit.
2. **Build**: `scripts/check_release.py` refuses a tag that disagrees
   with any version, has no CHANGELOG heading, or sits on a commit not in
   `main`'s history. Core is built once, and the wheel is installed and
   run as the tagged version.
3. **Publish**: Core to PyPI by trusted publishing (GitHub environment
   `pypi-core`); no token is stored.
4. **Release**: the GitHub release, with the CHANGELOG section as its
   notes and the integration zip. It comes last because the zip's
   `manifest.json` pins the Core just published.

Run by hand (Actions, Release, Run workflow), it builds and publishes to
Test PyPI (environment `test-pypi-core`) and creates no release.

## Before the First Release

Set up once, outside the repository, before the first tag. PyPI trusts
one workflow file by name, so each entry names `release.yml`
(REFERENCES.md § R25).

- [ ] **GitHub environments** `pypi-core` and `test-pypi-core` in the
      repository's settings.
- [ ] **PyPI pending publisher** (account sidebar, Publishing): project
      `solentlabs-internet-health-monitor-core`, owner `solentlabs`,
      repository `internet-health-monitor`, workflow `release.yml`,
      environment `pypi-core`.
- [ ] **Test PyPI pending publisher**: the same, environment
      `test-pypi-core`.
- [ ] **A manual run to Test PyPI**, to prove the workflow before the
      first tag.
- [ ] **The first tag soon after**: a pending publisher does not reserve
      the project name on PyPI until its first upload.

A project that moves publishing into another workflow file must change
its PyPI publisher in the same step, or its next upload is refused.
