# Internet Health Monitor - Roadmap

## Vision

The most comprehensive, easiest-to-configure network health monitoring integration for Home Assistant. Zero-config where possible, flexible where needed, rock-solid always.

**Part of the Solent Networks Suite** - designed for future correlation with Cable Modem Monitor and other network integrations.

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
3. **Bandwidth testing you control** - Tests run only from a button or your own automation, within data and daily limits
4. **Pluggable backends** - User picks the speed test service; each is a drop-in module that keeps to its provider's terms (docs/SPEED_TEST_BACKENDS.md)
5. **Unified configuration** - One integration, one options flow, done
6. **Correlation-ready** - Stable entity ids and units, combined with other integrations in HA (ADR-002)

---

## Where the Details Live

This roadmap tracks phases and decisions in progress. What IHM does is
specified once, where it is implemented:

| Topic | Doc |
| ------- | ----- |
| Entities and attributes | [README.md § Entities](../README.md#entities) |
| Options | [README.md § Configuration](../README.md#configuration) |
| Speed tests, backends, limits | [SPEED_TEST_BACKENDS.md](SPEED_TEST_BACKENDS.md) |
| Dashboard card and action | [DASHBOARD_CARD.md](DASHBOARD_CARD.md) |
| Layers, files, one poll, failure isolation, data leaving the host | [ARCHITECTURE.md](ARCHITECTURE.md) |

---

## Path to Release

Set 2026-11-18. Each stage finishes before the next starts. Cable Modem
Monitor is the reference for how each is done.

1. **Local.** Everything that can be built and tested locally is: core as
   a portable package (ADR-005), modular backends (ADR-003), tests and
   coverage gates, icon, configuration UX, a customizable entity name
   prefix, sensor history (long-term statistics), metrics.
2. **GitHub.** Push to `solentlabs/internet-health-monitor` with CI.
3. **PyPI.** Publish `solentlabs-internet-health-monitor-core`, the
   version `manifest.json` pins (ADR-005). HA installs it from there.
4. **Live HA.** Update the deployed HA to at least IHM's minimum (ADR-008),
   then install from GitHub and
   verify on a real network path (hops 2 and 3 cannot be seen from
   Docker Desktop: ARCHITECTURE.md).
5. **Publish.** Release zip installs, then HACS submission.

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
      hop IPs cached and re-detected on reset
- [x] Config toggles (gateway, DNS)
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
- [x] Run speed test button, and a nightly test (on or off, at a random
      time from 1 to 5 am; HA `appropriate-polling`, ADR-003)
- [x] Data limit per test, daily test limit and data budget per 30 days,
      on their own setup screen
- [x] Speed test sensors: download, upload, idle and loaded latency, data used

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
  - [x] Troubleshooting guide (README.md § Troubleshooting)
- [ ] Local testing
  - [x] Run on dev laptop (Docker HA harness, `make test-all`)
  - [ ] Deploy to a real HA instance (Path to Release stage 4)
- [ ] DevOps
  - [ ] GitHub repo under solentlabs org (stage 2)
  - [ ] CI/CD pipeline: workflows written (`.github/workflows/`), first run at stage 2
  - [ ] Branch protection (stage 2)
  - [ ] Release automation: `release.yml` and `publish.yml` written, first run at stages 2 and 3
- [ ] HACS submission (stage 5)

---

## Non-Goals (Out of Scope)

- **Reading other HA speed test integrations** - IHM runs its own tests (ADR-003)
- **Composite health scores** - Each entity reports one measurement; build composites in HA (ARCHITECTURE_DECISIONS.md ADR-004)
- **Correlation/diagnosis** - Done in HA over entities (ADR-002)
- **Historical storage** - HA recorder handles this
- **Alerting/notifications** - Use HA automations
- **Cloud telemetry** - All data stays local
- **Router/modem configuration** - Read-only monitoring

---

## Not Built

IPv6, custom hop targets, interface selection, SNMP router counters
and an Aggregator hook were considered and cut, each for a recorded
reason: ARCHITECTURE_DECISIONS.md § ADR-011.

---

## Success Criteria

**v1.0.0 is ready when:**

1. Zero-config setup works on fresh HA install
2. Every entity in README.md § Entities functional
3. Multi-hop latency is unique differentiator
4. Bandwidth testing is pluggable and runs from a button or automation
5. 90%+ test coverage
6. Multi-language support (six languages)
7. Tested on real HA instance (not just dev)
8. Documentation complete
9. HACS-ready

---

*Created: 2025-11-28*
*Updated: 2026-11-19*
*Status: Local stage (Path to Release stage 1)*

---

**Solent Labs™** - Network Monitoring Done Right
