# Contributing to Internet Health Monitor

Thank you for your interest in contributing. Bug reports with the
diagnostics download, documentation fixes, translations and tested fixes
are all welcome.

## Before you file

- **Bug reports:** file directly with the bug form; attach the
  diagnostics download.
- **Questions:** ask in [Discussions](https://github.com/solentlabs/internet_health_monitor/discussions).
- **New features, sensors, outside services or architecture changes:**
  start a [Discussion](https://github.com/solentlabs/internet_health_monitor/discussions/new?category=ideas),
  not an issue or a pull request. Issues are for features whose shape is
  already clear; Discussions are for shaping the idea.
- **Core changes** (`packages/internet_health_monitor_core/`): start a
  Discussion whatever the size. Core is the measurement engine every
  reading depends on, and its command line is used on its own.
- **Refactors touching more than two files:** start a Discussion. Small,
  scoped fixes can go straight to a pull request.

### Why scope before code

Review is the bottleneck on any project. Writing code is cheap, with or
without AI; reading it carefully is not. Agreeing on scope before code is
written keeps that cost down. The same
discipline is behind Rust's RFCs, Python's PEPs and Home Assistant's
[architecture repository](https://github.com/home-assistant/architecture).

## How changes are made

[CLAUDE.md](CLAUDE.md) states the project's rules, and the docs it
points to hold the detail. The ones that shape a contribution:

- **Use case, then spec, then a failing test, then code.** A feature
  starts from a use case in [docs/USE_CASES.md](docs/USE_CASES.md). The
  specs ([docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and the docs it
  links) are the authority: if code must differ from them, the spec
  changes first, in the same pull request.
- **Decisions are recorded.** A choice that constrains later work goes in
  [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md) as a
  proposed ADR; only the maintainer marks one accepted.
- **One measured value per entity.** Each sensor reports a measurement,
  an observed state, or a grade on a published, cited scale. No composite
  health scores or multi-signal verdicts
  ([ADR-004](docs/ARCHITECTURE_DECISIONS.md)); a proposal that interprets
  readings is a Discussion first.
- **Outside services only by the user's choice** ([ADR-006](docs/ARCHITECTURE_DECISIONS.md)):
  off by default, the option says what it sends and to whom, and
  ARCHITECTURE.md lists it. Speed test services also follow their
  provider's terms ([ADR-003](docs/ARCHITECTURE_DECISIONS.md)).
- **Claims are cited.** Thresholds, protocol details and provider terms
  cite an entry in [docs/REFERENCES.md](docs/REFERENCES.md).
- **Tests:** table-driven, no real network (ping, traceroute, DNS and
  speed tests are mocked or served in-process), and no personal data:
  use private ranges, documentation ranges and `example.com`
  (REFERENCES.md § R12).
- **Code:** measurement logic in Core imports nothing from Home
  Assistant; type hints throughout, mypy and pyright clean; no blocking
  I/O in the event loop.

## Development environment

[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) sets up either a local
Python environment or the dev container. Then:

- `make setup`, and `make setup-current` for the newest Home Assistant
  the tests support
- `make check`: lint, formatting, type checks, spelling and Markdown
- `make test-all`: the tests on both Home Assistant versions, with the
  coverage gates
- `make test-windows` (from WSL): Core's command line on Windows

To try the integration in a local Home Assistant, the VS Code tasks
**🚀 HA: Start** (or **🚀 HA: Start (Debug)**), **📋 HA: View Logs** and
**⏹️ HA: Stop** run it in a container with the code mounted. A container
on Docker Desktop sees only the first hop
([Known Limitations](https://github.com/solentlabs/internet_health_monitor#known-limitations)).

Never run a real speed test as part of development without meaning to:
it uses your data allowance and loads your household's connection.

## Submitting changes

Fork, branch, and open a pull request against `main`; the template
lists what it needs.

- **Before pushing:** the pre-commit hooks check formatting, lint, types,
  spelling and Markdown on each commit, and run `make check` and
  `make test-all` before each push (`pre-commit install --hook-type
  pre-commit --hook-type commit-msg --hook-type pre-push`). CI is the
  final gate.
- **CHANGELOG:** a pull request that changes code adds an entry under
  `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md); CI checks it.
- **Issues:** refer to them with `Related to #N`, never `Fixes #N` (see
  [Closing](#closing)).

### Commit message format

Commits follow [Conventional Commits](https://www.conventionalcommits.org/),
checked on every commit of a pull request against
[commitlint.config.js](commitlint.config.js) (the `commit-msg` hook uses
the same file):

```text
fix(dns): time the host's DNS server under the Supervisor

- The relay at 172.30.32.3 was being timed instead
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
`build`, `ci`, `chore`, `revert`, `deps`. Wrap body lines at 100
characters. The check reads every commit on the branch, so squash any
scaffolding commits (an AI agent's `Initial plan`, for example) before
pushing. A failing check is fixed in the commits or code it flags, never
by editing the check; a pull request that changes `.github/workflows/`
to pass its own gate is closed.

## Closing

**No issue is closed automatically.** `Fixes #N`, `Closes #N` and
`Resolves #N` in a commit close the issue when it merges, so use
`Related to #N` instead. An issue closes when the reporter confirms the
fix works for them, or, if they have left the conversation, by a
deliberate close from the maintainer.

A Discussion closes when it is answered, when what it asked for has
shipped, or when it has gone quiet after the last question put to it.
The closing comment says which, and points at what superseded it.
Closing is bookkeeping, not rejection: a comment on a closed thread is
still read and can reopen it.

## AI-assisted contributions

AI assistants (Claude Code, Cursor, Copilot and others) make code cheap
to write and do nothing for the cost of reviewing it. These rules apply
to any contribution made with one:

- **Disclose it** on your first pull request or issue: one sentence on
  which tool and what it did.
- **Give it this file.** Assistants load [CLAUDE.md](CLAUDE.md) (or
  their own instruction file) but not CONTRIBUTING.md, so they follow
  the code rules and skip the process ones: a pull request that should
  have been a Discussion, a Core change without one.
- **Read every line of the diff** before committing. Disclosure is not
  a substitute for reading.
- **One thread, one ask.** Three unrelated requests are three threads.

A contribution that skips these gets the same short reply every time:

> Thanks for the contribution. This needs scope discussion before code;
> please open a Discussion and we can scope it together there. Closing
> this for now; reopen or refile once the Discussion lands.

### Review pace

Reviews happen on weekends, about two weeks each, and one pull request
per contributor is active at a time; more are sequenced, not reviewed in
parallel ([SUPPORT.md](SUPPORT.md)).

## Translations

The integration's text is in `custom_components/internet_health_monitor/strings.json`
(English) and `translations/` (German, Spanish, French, Brazilian
Portuguese and Simplified Chinese, plus English). To add a language,
copy `translations/en.json` to `translations/<code>.json` and translate
the values, never the keys. A test fails if a translation's keys differ
from `strings.json`'s.

## Code of conduct

Everyone taking part agrees to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions

See [SUPPORT.md](SUPPORT.md) for where each kind of question goes.
