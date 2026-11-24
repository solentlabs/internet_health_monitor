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

`main` takes changes only through a pull request (its rulesets), so a
release is a pull request, a merge, then a tag. The developer stages
and approves; Claude carries it from commit to published
release and stops at the first failure.

**Prepare** (Claude, then the developer):

1. Run `make test-windows` from WSL: Core's command line on your Windows
   Python, with real pings and a trace. CI tests Core on Windows, but
   GitHub's runners block outbound ping, so only this checks the real
   probes.
2. Set the version in the four places and rename CHANGELOG.md's
   `## [Unreleased]` to the version's heading. Run the tests,
   `scripts/check_changelog.py` and `scripts/check_release.py vX.Y.Z`.
3. The developer stages the changes and approves the release. That one
   approval covers every Ship step while CI stays clean.

**Ship** (Claude):

1. Pull `main`, create a `release/X.Y.Z` branch, commit exactly what is
   staged, push the branch and open a pull request.
2. When every check passes, merge it with a merge commit (the admin
   bypass stands in for the approving review) and delete the branch on
   GitHub and locally (`gh pr merge --merge --admin --delete-branch`).
   Then `git fetch --prune` and delete any other branch already merged
   into `main`, here or on GitHub; leave an unmerged one and name it to
   the developer.
3. Tag the merge commit and push the tag, which starts `release.yml`:

   ```bash
   git tag vX.Y.Z <merge-commit> && git push origin vX.Y.Z
   ```

4. When the workflow finishes, check that the GitHub release carries
   `internet_health_monitor.zip`, PyPI shows Core at the version, and
   HACS offers the update. HACS reads releases on its own; nothing is
   submitted.
5. Tell a leadline session the version is released (§ Metrics) and add
   a journal entry.

A failed check, a review comment or a failed workflow step stops the
release: Claude reports it to the developer and waits. Nothing is
re-run, skipped or forced past a failure without the developer's word.
If a pre-commit hook fails, Claude fixes the file and the developer
stages it again; Claude never stages.

`release.yml` (Ship step 3) runs these, each only if the one before passed:

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
its section replaces the betas' sections and describes what that version
is, written for someone upgrading from the last final version (or, for
0.1.0, installing it fresh); fixes between betas are left out. Each beta's
notes stay on its GitHub pre-release.

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
- [x] **What HACS checks** (hacs.xyz, "Include default repositories"): a
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

- [x] **Push day:** the nightly job's GitHub token covers this repository,
      with push access (traffic needs it).
- [x] **Within 14 days of the push:** a leadline session adds the GitHub
      entries (traffic, issues, response times, releases, contributor
      locations; discussions if Discussions is on) and the trends page
      `internet_health_monitor_trends.html`. GitHub keeps traffic for 14
      days.
- [x] **Push day:** tell a leadline session the repository is pushed, and
      whether Discussions is on. That starts leadline's 14-day window, and
      leadline passes it to the operations session, which adds IHM to the
      morning briefing.
- [x] **Release day:** tell a leadline session the version is released.
- [x] **After the first PyPI publish:** Core in leadline's `pypi` list.
- [ ] **After the HACS listing, or a forum thread:** leadline's
      `ha_integration` and `discourse_topics` entries.
