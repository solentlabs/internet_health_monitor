# Architecture Decisions

ADR-style record. **Open** entries carry analysis and a recommendation;
only the developer marks one Accepted. Accepted entries state the
constraint they create. Sources: [REFERENCES.md](REFERENCES.md) (`R<n>`).
Use cases: [USE_CASES.md](USE_CASES.md) (`UC-<n>`).

| ADR | Topic | Status |
|-----|-------|--------|
| [001](#adr-001-bufferbloat-is-measured-passively-in-ihm) | Bufferbloat is measured passively in IHM | Accepted 2026-11-18 |
| [002](#adr-002-ihm-stays-a-standalone-integration) | IHM stays a standalone integration | Accepted 2026-11-18 |
| [003](#adr-003-speed-testing-with-user-selected-backends-roadmap-phase-3) | Speed testing with user-selected backends (ROADMAP Phase 3) | Accepted 2026-11-18 |
| [004](#adr-004-no-composite-health-sensors) | No composite health sensors | Accepted 2026-11-18 |
| [005](#adr-005-core-runs-anywhere) | Core runs anywhere | Accepted 2026-11-18 |
| [006](#adr-006-no-third-party-lookups) | No third-party lookups | Open |

---

## ADR-001: Bufferbloat is measured passively in IHM

**Status:** Accepted 2026-11-18

**Context:** A separate Solent Labs project, BufferBloat, was designed
(never built or committed) as an active latency-under-load test
following the IETF responsiveness draft (R1). It is folded into IHM and
its repo retired. This ADR is the surviving record.

**Why not a standalone active test** (IHM's own opt-in speed tests are
ADR-003):
- soulripper13/hass-speedtest-ookla (HACS default) already reports
  loaded latency per direction and a "Bufferbloat Grade" (R8). A
  standalone active test would add only the IETF method, a
  Waveform-matching grade (R3), a busy-line pre-check and LAN testing.
- No permitted internet load server. Cloudflare's speed test endpoints
  have no published permission for scheduled automated use and none was
  obtained (R5); Apple's has none either (R2). Self-hosted servers need
  setup most users won't do.
- An active test causes the bloat it measures and costs data: about
  145 MB per run on a 100/10 line [C], 1.4 to 2.8% of a 1.25 TB cap at
  one run every 6 h.

**Decision:** IHM detects bufferbloat **passively**, from latency it
already measures. Household traffic (the motivating case: camera video
filling a 10 Mbps uplink while cloud gaming lags, see USE_CASES.md)
shows as first-ISP-hop latency rising above its idle baseline while
gateway latency stays flat. A gateway rise instead points to LAN or
Wi-Fi queueing (UC-8). It costs almost no data, loads nobody's servers,
and graphs in HA against the camera's streaming state.

**Constraints:**
- The passive signal works with no active test configured. Active
  tests are separate and opt-in
  ([ADR-003](#adr-003-speed-testing-with-user-selected-backends-roadmap-phase-3)).
- Gateway and first-ISP-hop latency stay separate entities in ms with
  stable entity ids, so the comparison can be made in HA.

**Verify before relying on it** (Open Verification Items in
REFERENCES.md):
1. ISP routers may deprioritize ICMP aimed at themselves, so a stable
   host just past the first hop may be the better target. Needs a
   citation, not recall.
2. The default 60 s / 3-ping poll likely misses short spikes; bloat
   tracking probably needs about 1 ping/s to the hop target.
3. Zero-cost field check: ping hop 2 of `traceroute -n 1.1.1.1` while
   someone opens the camera live view; watch whether it climbs while the
   gateway stays flat.

---

## ADR-002: IHM stays a standalone integration

**Status:** Accepted 2026-11-18

**Question:** Merge IHM into Cable Modem Monitor (CMM)?

**Decision:** No. IHM stays its own integration.

**Rationale:**
- **Audience.** Gateway, DNS, hop and bloat monitoring apply to any ISP
  (fiber, DSL, 5G, cable). CMM's identity, setup flow and modem catalog
  are cable-only; non-cable users would never find these features inside
  it.
- **Scope.** CMM reads the modem. Probing hosts beyond the modem is a
  different job.
- **Cost of standing alone, offset.** IHM reuses CMM's patterns, not its
  code: the fast-cadence ICMP/TCP/HTTP HEAD probes independent of the
  data poll, with tests, in CMM's
  `packages/cable_modem_monitor_core/solentlabs/cable_modem_monitor_core/orchestration/modem_health.py`,
  and CMM's CI, release and HACS tooling.

**Constraints:**
- No code dependency between IHM and CMM in either direction.
- Combined diagnosis happens in HA over entities (UC-7). Three ping
  points localize a queue: router (IHM gateway), modem (CMM modem ping
  latency) and first ISP hop (IHM). ISP hop rising while modem ping
  stays flat under load puts the queue in the modem's upstream (DOCSIS)
  buffer, not LAN/Wi-Fi. IHM therefore keeps stable entity ids and ms
  units.
- ROADMAP non-goal "Cloud telemetry: all data stays local" stands. Any
  future telemetry would be a separate, opt-in consumer of HA entities,
  never code inside IHM.

---

## ADR-003: Speed testing with user-selected backends (ROADMAP Phase 3)

**Status:** Accepted 2026-11-18 (backend list pending research)

**Question:** Keep ROADMAP Phase 3, given hass-speedtest-ookla (R8)
already ships throughput, loaded latency and a bloat grade?

**Decision:** Keep it, and do it better than R8:
- **Modular backends.** Every backend implements one shared interface
  (run a test, return download, upload, idle latency and loaded latency
  per direction where the API provides them). Adding a bandwidth API
  means adding one module; nothing else changes.
- **User selects the backend.** No lock-in to one provider.
- **First backend: M-Lab NDT7** (decided 2026-11-18). The order of the
  rest is open; the interface must not assume any one provider.
- **IHM runs its own tests.** No backend reads another HA integration's
  sensors (decided 2026-11-18): IHM is meant to replace those
  integrations, not depend on them. The backend
  list comes from a research pass across available services (Open
  Verification Items), not from the current ROADMAP list alone.
- **Bufferbloat included.** Each active test reports idle and loaded
  latency per direction, complementing ADR-001's passive signal.
- **No server to run.** No backend requires the user or Solent Labs to
  host a server.
- **Fix R8's known gaps:** loaded-latency sensors keep long-term
  statistics, a failed test is visible rather than leaving stale values,
  and no test runs on HA restart.

**Constraints** (relaxed 2026-11-18, see Permission below):
- A backend may use a public endpoint without written permission
  (R5 Cloudflare, R9), provided:
  - the default schedule is modest, and the provider's published limits
    apply where they exist (R9: M-Lab, about 4 a day);
  - requests identify IHM honestly (User-Agent or client name);
  - the docs state IHM is not affiliated with the provider.
- No backend accepts a licence or terms on the user's behalf. The Ookla
  CLI is excluded: hass-speedtest-ookla runs it with `--accept-license
  --accept-gdpr` (R8), and its EULA is "personal, non-commercial use".
- Client libraries must have a licence compatible with distribution
  (R5: cloudflarepycli is GPL-3.0 and not used).
- Tests never run without explicit user configuration (ROADMAP Tier 3).

**Permission:** The original rule required a recorded permission basis
for every backend. Other HA integrations call these endpoints with no
published permission (R8: ha-cloudflare-speed-test runs hourly against
speed.cloudflare.com by default), so that rule left IHM unable to match
them. Asking Cloudflare in writing remains open to the developer.

---

## ADR-004: No composite health sensors

**Status:** Accepted 2026-11-18

**Question:** Keep the planned 0-100 `connection_quality` sensor and the
`connection_healthy` composite binary sensor (ROADMAP Tier 1)?

**Decision:** Drop both. Neither was implemented.

**Rationale:**
- A composite hides which signal moved. Localizing a problem (ISP hop
  rising while the gateway stays flat, ADR-001) depends on seeing the
  signals separately.
- Weights and good/fair cutoffs would be our invention, with no source
  to cite.
- Users who want one signal build it in HA with their own thresholds.
  `docs/dashboard-examples.md` § Build Your Own Health Check gives a
  template.

**Constraint:** Every IHM entity reports one observed measurement or
state. `gateway_reachable` and `internet_reachable` stay: each reports
one directly observed state.

---

## ADR-005: Core runs anywhere

**Status:** Accepted 2026-11-18

**Decision:** The measurement core is a standalone Python package under
the Solent Labs namespace, following Cable Modem Monitor's packaging
(`solentlabs.cable_modem_monitor_core`). It can run outside Home
Assistant: a CLI, a cron job, a Windows service or scheduled task. Each
host is a thin adapter over the same core; the HA integration is one of
them.

**Constraints:**
- Core imports nothing from `homeassistant` and holds no host-specific
  scheduling, config storage or UI.
- Core's results are plain data (dataclasses), so any adapter can map
  them.
- A browser extension cannot send ICMP or run traceroute; it would reach
  core through a native helper, or measure HTTP timing only. Neither is
  planned.

---

## ADR-006: No third-party lookups

**Status:** Open. Recommendation: accept.

**Context:** Hop enrichment sent each public hop IP to ip-api.com over
plain HTTP and the gateway's MAC address to api.macvendors.com. Neither
is a measurement, and both tell a third party about the user's network.

**Decision:**
- IHM sends nothing to a third party except the probes themselves and,
  when enabled, the user-selected speed test backend (ADR-003).
- Hop hostnames come from reverse DNS through the resolver the host
  already uses. Nothing else enriches a hop.

**Constraints:** A feature that needs a new external lookup needs a new
ADR. `docs/ARCHITECTURE.md § Data Leaving the Host` lists every
destination.
