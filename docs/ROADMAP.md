# Internet Health Monitor - Roadmap

## Vision

The most comprehensive, easiest-to-configure network health monitoring integration for Home Assistant. Zero-config where possible, flexible where needed, rock-solid always.

A Solent Labs project, alongside Cable Modem Monitor.

---

## Why This Exists

| Existing Solution | Problem |
| ------------------- | --------- |
| HA Ping integration | One host per entry, added by hand; no view of the path's hops |
| HA Speedtest.net | No scheduling control, runs whenever, heavy |
| HANetProbe | Requires MQTT broker + external daemon |
| DIY template sensors | Fragile, no auto-detection, maintenance burden |

**Our answer:** One integration that does it all - auto-detects everything, surfaces clean sensors, and prepares data for correlation.

---

## Differentiators

1. **Zero-config auto-detection** - Gateway, DNS, ISP hops discovered automatically
2. **Multi-hop network path visibility** - Latency at each hop (1, 2, 3+) - unique in HA ecosystem
3. **Bandwidth testing you control** - Whole tests over frequent ones: automatic tests spaced to fit your data budget (weekly without one), each sized from the last result, with the working shown; a button; a daily limit and an optional 30-day data budget
4. **Bufferbloat, graded and localized** - Latency increase under load per direction and Waveform's grade from each speed test; hop latency between tests shows where a queue sits
5. **Pluggable backends** - User picks the speed test service; each is a drop-in module that keeps to its provider's terms (docs/SPEED_TEST_BACKENDS.md)
6. **Unified configuration** - One integration, one options flow, done
7. **Correlation-ready** - Stable entity ids and units, combined with other integrations in HA (ADR-002)

---

## Where the Details Live

This roadmap tracks phases and decisions in progress. What IHM does is
specified once, where it is implemented:

| Topic | Doc |
| ------- | ----- |
| Entities and attributes | [.github/README.md § Entities](../.github/README.md#entities) |
| Options | [.github/README.md § Configuration](../.github/README.md#configuration) |
| Speed tests, backends, limits | [SPEED_TEST_BACKENDS.md](SPEED_TEST_BACKENDS.md) |
| Dashboard card and action | [DASHBOARD_CARD.md](DASHBOARD_CARD.md) |
| Layers, files, one poll, failure isolation, data leaving the host | [ARCHITECTURE.md](ARCHITECTURE.md) |

---

## Path to Release

Set 2026-11-18. Each stage finishes before the next starts. Cable Modem
Monitor is the reference for how each is done.

1. **Local.** Everything that can be built and tested locally is: core as
   a portable package (ADR-005), modular backends (ADR-003), tests and
   coverage gates, icon, configuration UX, names changed by renaming the
   device (ADR-010), sensor history (long-term statistics by choice,
   ADR-013), metrics.
2. **GitHub.** Push to `solentlabs/internet_health_monitor`, public,
   with CI and branch protection.
3. **Betas, tested live.** Release `0.1.0b1` (docs/RELEASING.md § Beta
   Releases): Core on PyPI and the zip as pre-releases. Update the
   deployed HA to at least IHM's minimum (ADR-008), install the beta
   through HACS as a custom repository, and verify on a real network
   path (hops 2 and 3 cannot be seen from Docker Desktop:
   ARCHITECTURE.md). Fixes ship as the next beta.
4. **0.1.0.** Released once the live checks pass. From here HA installs
   Core from PyPI at a final version.
5. **Publish.** HACS submission.

---

## Implementation Checklist

### Phase 1: Core Foundation ✓ (Existing)

- [x] Gateway latency/jitter/packet loss
- [x] ISP hop detection
- [x] DNS latency
- [x] Config flow + options flow
- [x] Refresh/reset buttons
- [x] DataUpdateCoordinator pattern
- [x] Basic tests

### Phase 2: Multi-Hop & Polish

- [x] Multi-hop: hops 1 to 3, each with latency, jitter and loss sensors;
      hop IPs cached; re-traced when the gateway changes and every 10
      minutes while hops are missing
- [x] Internet reference: a fourth ping target past the ISP (ADR-015)
- [x] Binary sensors (gateway reachable, internet reachable)
- [x] Solent Labs branding in device info and integration icon
- [x] Core as a portable package with a command line (ADR-005)
- [x] Core on Linux and Windows behind one platform interface (ADR-005)
- [x] Bundled dashboard card, following CMM's pattern (pattern reuse, no
      code dependency: ARCHITECTURE_DECISIONS.md ADR-002). Reference:
      CMM `custom_components/cable_modem_monitor/docs/DASHBOARD_CARD_SPEC.md`
      and `card/`.
  - [x] Card in the dashboard's Add card list, configured by form, no YAML
  - [x] `generate_dashboard_card` action returning the card's YAML
  - [x] Card failing to load never stops monitoring
  - [x] Shows each measurement separately (no composite, ADR-004)

### Phase 3: Bandwidth Testing

- [x] Core speed test interface and result (`speed_test.py`, ADR-003)
- [x] Backends, one module each (docs/SPEED_TEST_BACKENDS.md)
  - [x] Cloudflare
  - [x] M-Lab NDT7, with consent and its automated-client rules
  - [x] LibreSpeed
  - Fast.com: cut, Netflix's terms forbid automated access (ADR-003)
- [x] Run speed test button, and automatic tests (on or off, at a random
      time from 1 to 5 am, spaced by the data budget; HA
      `appropriate-polling`, ADR-003)
- [x] Data limit per test (automatic by default), daily test limit and
      data budget per 30 days, on their own setup screen, which shows its
      working (.github/README.md § How Much Data Speed Tests Use)
- [x] Speed test sensors: download, upload (each saying what ended it),
      idle and loaded latency, data used
- [x] Bufferbloat: latency increase per direction and Waveform's grade
      (R3, ADR-004 amendment)

### Phase 4: Environment Detection

Decided 2026-11-19: build both, as diagnostic sensors.

- [x] Connection type detection (wifi/ethernet), from the default route's interface
- [x] Install type: HA's own `system_info`, not detected by Core
- [x] Sensors for each

### Phase 5: Quality & Release

- [x] Multi-language support: de, es, fr, pt-BR, zh-CN, plus en
- [x] Comprehensive test coverage
  - [x] Unit tests for all core modules
  - [x] Integration tests on a real in-memory HA (`tests/components/conftest.py`)
  - [x] Mock external tools (ping, traceroute) and in-process fakes of each speed test provider
  - [x] Security review (no command injection, etc.): ARCHITECTURE.md § Security
- [x] Documentation
  - [x] README with examples
  - [x] Dashboard examples
  - [x] Troubleshooting guide (.github/README.md § Troubleshooting)
- [x] Local testing
  - [x] Run on dev laptop (Docker HA harness, `make test-all`)
  - [x] Deploy to a real HA instance (Path to Release stage 3)
    - [x] Hops 2 and 3 detected, and their hostnames redacted in the
          diagnostics download (2026-11-23: detected on HA OS; these hops
          have no hostnames, so redaction rests on its tests)
    - [x] A speed test fills the bufferbloat grade and increases; the
          setup screen's working matches the result
    - [x] Passive bufferbloat field check (ADR-001 item 3): hop 2 flat
          while the camera live view ran (2026-11-23), and a full-upload
          speed test raised latency only 11 ms, so the line has no bloat
          to catch. No faster probe for 0.1.0 (ADR-001 § Field check)
- [x] Before 0.1.0
  - [x] Screenshots in light and dark, in both READMEs (light `name.png`,
        dark `name-dark.png`, as Cable Modem Monitor)
    - [x] The full card, light (`images/dashboard-screenshot.png`)
    - [x] The full card, dark (`images/dashboard-screenshot-dark.png`)
    - [x] A card per hop, light and dark (`images/hop-cards.png`,
          `images/hop-cards-dark.png`)
    - [x] The combined Network path card, light and dark
          (`images/network-path-card.png`, `images/network-path-card-dark.png`)
    - [x] The settings screens, light and dark (`images/settings.png`,
          `images/settings-speed-tests.png` and their `-dark` versions)
- [x] DevOps
  - [x] GitHub repo under solentlabs org (stage 2)
  - [x] CI/CD pipeline: workflows written (`.github/workflows/`), first run at stage 2
  - [x] Branch protection (stage 2)
  - [x] Release automation: one `release.yml` (CI, checks, PyPI, then the GitHub release; docs/RELEASING.md), first run at stage 3
- [x] HACS submission (stage 5): in the default list (hacs/default#14834)

---

## Non-Goals (Out of Scope)

- **Reading other HA speed test integrations** - IHM runs its own tests (ADR-003)
- **Composite health scores** - Each entity reports one measurement, or one grade on a cited scale; build composites in HA (ARCHITECTURE_DECISIONS.md ADR-004)
- **Correlation/diagnosis** - Done in HA over entities (ADR-002)
- **Historical storage** - HA recorder handles this
- **Alerting/notifications** - Use HA automations
- **Cloud telemetry** - All data stays local
- **Router/modem configuration** - Read-only monitoring

---

## After 0.1.0

IHM stays on 0.x for now: it is in the Marketplace but not yet
promoted. Below, in priority order; each starts only when its gate is
met.

| # | Item | Gate |
| - | ---- | ---- |
| 1 | **DNS resolver comparison** (decided 2026-11-23): opt-in, the same uncached lookup timed against a few public resolvers beside the user's own, one sensor each, and its own card part | A use case asks for it; then its ADR and each provider's terms for DNS queries, since it is a new outside service (ADR-006) |
| 2 | **IPv6** | A user who needs it; ADR-014 names where it would be added |

## Not Built

Custom hop targets, interface selection, SNMP router counters and an
Aggregator hook were considered and cut, each for a recorded reason:
ARCHITECTURE_DECISIONS.md § ADR-011.

---

## Success Criteria

**v1.0.0 is ready when:**

1. Zero-config setup works on fresh HA install
2. Every entity in .github/README.md § Entities functional
3. Multi-hop latency is unique differentiator
4. Bandwidth testing is pluggable and runs automatically, from a button or from an automation
5. Test coverage above 95% for the HA layer and 90% for Core
6. Multi-language support (six languages)
7. Tested on real HA instance (not just dev)
8. Documentation complete
9. HACS-ready

---

*Created: 2025-11-28*
*Updated: 2026-11-24*
*Status: 0.1.1 released and in HACS's default list, not yet promoted; soaking (Path to Release complete)*
