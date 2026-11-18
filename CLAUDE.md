# Claude Rules

> **This file**: how Claude behaves in this repository. Architecture,
> specs and decisions live in the docs below; this file points rather
> than restates. Global rules (`~/.claude/CLAUDE.md`: git index, working
> style) apply on top. Mirrors Cable Modem Monitor's `CLAUDE.md`, which
> is the reference for anything not covered here.

## Project

Internet Health Monitor (IHM) is a Home Assistant integration (domain
`internet_health_monitor`) that monitors the path from the HA host to
the internet: gateway, ISP hops and DNS latency, jitter and loss,
passive bufferbloat, and optional speed tests through drop-in backends.
It is a standalone Solent Labs integration with no code dependency on
Cable Modem Monitor (`docs/ARCHITECTURE_DECISIONS.md` § ADR-002).

## Where Things Live

| Topic | Authoritative doc |
| ----- | ----------------- |
| Layers, data flow, data leaving the host, neighbours | `docs/ARCHITECTURE.md` |
| Features, phases, non-goals | `docs/ROADMAP.md` |
| Who uses this and why (drives tests) | `docs/USE_CASES.md` |
| Decisions, open and settled | `docs/ARCHITECTURE_DECISIONS.md` |
| Sources, licences, evidence labels | `docs/REFERENCES.md` |
| Speed test backends compared | `docs/SPEED_TEST_BACKENDS.md` |
| User-facing overview | `README.md` |

## Core Principles

Hard constraints. When in doubt, the principle wins over convenience.

### Docs

- **Standard doc set.** A human-readable architecture doc, spec docs,
  use cases and a decisions doc. Write each for a person reading it cold,
  not only for Claude.
- **Specs are the authority.** Code follows specs. If code must diverge,
  update the spec first, then the code, in the same change.
- **Decisions land in docs, not conversation.** A decision that
  constrains future work goes in `docs/ARCHITECTURE_DECISIONS.md` before
  the session ends. Only the developer marks an ADR Accepted.
- **Single source of truth.** State each fact once and link to it
  (`FILE.md § Section`). Docs state the current contract only; git
  carries history.
- **Every non-native claim carries a citation.** Thresholds, protocol
  details, licence terms and provider policies cite a
  `docs/REFERENCES.md` entry with its [V]/[U]/[C] label. Recalled values
  are not sources.
- **Write for brevity, then cut again.** No em-dashes, no marketing
  gloss.

### Design

- **Separation of concerns.** Measurement logic has no `homeassistant`
  import; the HA layer adapts results to entities. Each speed test
  backend is one module behind one interface (ADR-003).
- **KISS.** The simplest design that meets the use case. No options,
  flags or infrastructure until a use case needs them.
- **Measure what we observe; don't infer.** Each entity reports one
  measured value or observed state. No composite scores, confidence
  scores or multi-signal voting (ADR-004).
- **Don't load what we may not load.** Speed test backends follow
  ADR-003's conditions. Never accept a licence or terms on the user's
  behalf.

### Code

- **TDD.** Use case → failing test → implementation. Every spec
  requirement maps to at least one test.
- **Table-driven tests**, tables at the top of the file, consumed by
  `@pytest.mark.parametrize`.
- **No real network in tests.** Ping, traceroute, DNS and speed test
  backends are mocked or served in-process.
- **No blocking I/O in the event loop.**
- **Type hints required**; mypy and pyright clean. `Literal` over `str`
  enums.
- **One-line docstrings** on functions and classes; module docstrings
  required.

## Process

- **Never run a real speed test from a dev session** without asking: it
  uses the developer's data cap and loads the household's connection.
- **No external action without discussion, per action** (issue, PR,
  push, release, contacting a provider).
- **Stop on placeholders** (`TODO`, `TBD`, `XXX`) and flag them.
