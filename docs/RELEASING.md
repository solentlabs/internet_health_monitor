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

Semantic Versioning, from 0.1.0. Core is a library others can import, so
its version says when an upgrade breaks something, which a date cannot;
IHM releases when there is something to ship, not on a calendar as Home
Assistant does. 0.x until ROADMAP.md's v1.0.0 criteria are met.

One version, in four places that must agree:

- Core's `packages/internet_health_monitor_core/pyproject.toml`
- `manifest.json` `version`, and its pin of Core
- `const.py` `VERSION` (`tests/components/test_const.py` checks it
  against the manifest)

CHANGELOG.md has a heading `## [X.Y.Z] - YYYY-MM-DD` for it. A version
with a letter (`0.2.0b1`, PEP 440) becomes a GitHub pre-release.

## To Release

1. Run `make test-windows` from WSL: Core's command line on your Windows
   Python, with real pings and a trace. CI tests Core on Windows, but
   GitHub's runners block outbound ping, so only this checks the real
   probes.
2. In one commit on `main`: set the version in the four places and
   rename CHANGELOG.md's `## [Unreleased]` to the version's heading.
3. Push a tag `v` and the version:

   ```bash
   git tag v0.1.0 && git push origin v0.1.0
   ```

The workflow then runs, each step only if the one before passed:

1. **CI**: `tests.yml` on the tagged commit, Core on Linux and Windows
   included.
2. **Build**: `scripts/check_release.py` refuses a tag that disagrees
   with any version, has no CHANGELOG heading, or sits on a commit not in
   `main`'s history. Core is built once, and the wheel is installed and
   run as the tagged version.
3. **Publish**: Core to PyPI by trusted publishing (GitHub environment
   `pypi-core`); no token is stored.
4. **Release**: the GitHub release, with the CHANGELOG section as its
   notes and the integration zip. It comes last because the zip's
   `manifest.json` pins the Core just published.

There is no Test PyPI run: betas on the real PyPI are the rehearsal, each
one the whole path a final release takes (decided 2026-11-23, after five
betas).

## Beta Releases

A beta is a release whose version carries `b` and a number (`0.1.0b1`).
It goes through the same workflow: Core reaches PyPI as a pre-release,
which pip and HA install only when pinned, and the integration zip
becomes a GitHub pre-release.

Betas are how a version is tested on a real HA before it is final. In
HACS, add this repository under **Custom repositories** (category
Integration), turn on **Show beta** for it, and install. A fix ships as
the next beta (`0.1.0b2`), which HACS offers as an update.

Each beta gets its own CHANGELOG heading. When the final version ships,
the headings of its betas become that version's one heading, since the
betas' notes are what the version holds.

## Before the First Release

Set up once, outside the repository, before the first tag. PyPI trusts
one workflow file by name, so each entry names `release.yml`
(REFERENCES.md § R25).

- [x] **GitHub environment** `pypi-core` in the repository's settings.
- [x] **PyPI pending publisher** (account sidebar, Publishing): project
      `solentlabs-internet-health-monitor-core`, owner `solentlabs`,
      repository `internet_health_monitor`, workflow `release.yml`,
      environment `pypi-core`.
- [x] **The first tag soon after**, a beta: a pending publisher does not
      reserve the project name on PyPI until its first upload.

A project that moves publishing into another workflow file must change
its PyPI publisher in the same step, or its next upload is refused.

## Repository Checks

Workflows ported from Cable Modem Monitor: commit messages
(`commit-lint.yml`, rules in `commitlint.config.js`), CHANGELOG structure
and an entry for code changed into `main` (`changelog-check.yml`,
`scripts/check_changelog.py`), a note to contributors whose commits carry
a personal email (`check-commit-email.yml`; it names the commit, never the
address), HACS validation (`validate.yaml`), the devcontainer build
(`devcontainer.yml`), and CodeQL (`codeql.yml`: Python and the card's
JavaScript, on pushes and PRs to `main` and weekly; a workflow rather
than GitHub's default setup, so `main`'s ruleset can require it). Set up
once on GitHub:

- [x] **CodeQL's checks required** in `main`'s `require-status-checks`
      ruleset, once the workflow has run: `Analyze Code Security
      (python)` and `Analyze Code Security (javascript-typescript)`.
- [ ] **What HACS checks** (hacs.xyz, "Include default repositories"): a
      repository description, topics, issues on, and a full GitHub
      release; `validate.yaml` and `hassfest.yml` pass with no errors or
      ignores.
- [x] **The email check on a throwaway PR** with a `test@example.com`
      commit: the comment names the commit, and the address appears in
      neither the comment nor the run log.
- [x] **Your own pushes:** GitHub's "Block command line pushes that expose
      my email" is on.

## Metrics

Collected nightly by leadline-metrics, on the pattern of Cable Modem
Monitor's. Each entry goes into leadline's config only once its target
exists, since a missing repo, package or integration fails the nightly
run; a leadline session adds them.

- [ ] **Push day:** the nightly job's GitHub token covers this repository,
      with push access (traffic needs it).
- [ ] **Within 14 days of the push:** a leadline session adds the GitHub
      entries (traffic, issues, response times, releases, contributor
      locations; discussions if Discussions is on) and the trends page
      `internet_health_monitor_trends.html`. GitHub keeps traffic for 14
      days.
- [ ] **Push day:** tell a leadline session the repository is pushed, and
      whether Discussions is on. That starts leadline's 14-day window, and
      leadline passes it to the operations session, which adds IHM to the
      morning briefing.
- [ ] **Release day:** tell a leadline session the version is released.
- [ ] **After the first PyPI publish:** Core in leadline's `pypi` list.
- [ ] **After the HACS listing, or a forum thread:** leadline's
      `ha_integration` and `discourse_topics` entries.
