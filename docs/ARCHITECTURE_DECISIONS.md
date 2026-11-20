# Architecture Decisions

ADR-style record. **Open** entries carry analysis and a recommendation;
only the developer marks one Accepted. Accepted entries state the
constraint they create. Sources: [REFERENCES.md](REFERENCES.md) (`R<n>`).
Use cases: [USE_CASES.md](USE_CASES.md) (`UC-<n>`).

| ADR | Topic | Status |
| ----- | ------- | -------- |
| [001](#adr-001-bufferbloat-is-measured-passively-in-ihm) | Bufferbloat is measured passively in IHM | Accepted 2026-11-18; rationale refreshed, Open |
| [002](#adr-002-ihm-stays-a-standalone-integration) | IHM stays a standalone integration | Accepted 2026-11-18 |
| [003](#adr-003-speed-testing-with-user-selected-backends) | Speed testing with user-selected backends | Open |
| [004](#adr-004-no-composite-health-sensors) | No composite health sensors | Accepted 2026-11-18; amendment Open |
| [005](#adr-005-core-runs-anywhere) | Core runs anywhere | Accepted 2026-11-18 |
| [006](#adr-006-outside-services-only-by-user-choice) | Outside services only by user choice | Accepted 2026-11-19 |
| [007](#adr-007-fixed-60-second-polling) | Fixed 60-second polling | Accepted 2026-11-19 |
| [008](#adr-008-minimum-home-assistant-202610) | Minimum Home Assistant 2026.10 | Accepted 2026-11-19 |
| [009](#adr-009-jitter-is-consecutive-delay-variation) | Jitter is consecutive delay variation | Accepted 2026-11-19 |
| [010](#adr-010-names-are-changed-by-renaming-the-device) | Names are changed by renaming the device | Accepted 2026-11-19 |
| [011](#adr-011-roadmap-features-not-built) | Roadmap features not built | Accepted 2026-11-19; one row added, Open |
| [012](#adr-012-reachability-confirms-before-off-and-re-checks-fast-while-off) | Reachability confirms before off and re-checks fast while off | Accepted 2026-11-19 |
| [013](#adr-013-long-term-statistics-only-where-they-serve-a-use) | Long-term statistics only where they serve a use | Open |
| [014](#adr-014-ipv4-path-ready-for-ipv6) | IPv4 path, ready for IPv6 | Open |

---

## ADR-001: Bufferbloat is measured passively in IHM

**Status:** Accepted 2026-11-18. The rationale below was refreshed on
2026-11-20, once ADR-003's active tests graded bufferbloat; the decision
and constraints are unchanged. The refresh awaits the developer's Accept.

**Context:** A separate Solent Labs project, BufferBloat, was designed
(never built or committed) as an active latency-under-load test
following the IETF responsiveness draft (R1). It is folded into IHM and
its repo retired. This ADR is the surviving record.

**Why passive, alongside active tests** (IHM's opt-in speed tests,
ADR-003, measure the latency increase under load and grade it on
Waveform's scale, R3):

- An active test causes the bloat it measures and costs data, about
  140 MB on a 100/10 line (README.md § How Much Data Speed Tests Use),
  so IHM runs one at most nightly, overnight. Bloat from household
  traffic comes and goes during the day; only an always-on signal sees
  it.
- The passive signal needs no outside service and no setup; active
  tests need a provider the user chooses (ADR-006).
- A standalone active test of its own (the IETF method, R1) would add
  little over ADR-003's tests and hass-speedtest-ookla's (R8).

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
  ([ADR-003](#adr-003-speed-testing-with-user-selected-backends)).
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

## ADR-003: Speed testing with user-selected backends

**Status:** Open. Rewritten to state the current decision; awaiting the developer's Accept.

**Question:** Offer active speed tests, given hass-speedtest-ookla (R8)
already ships throughput, loaded latency and a bloat grade?

**Decision:** Yes, done better than R8.

- **One interface, one module per backend.** Each backend runs a test and
  returns download, upload, idle latency, loaded latency per direction
  and the data it used (Core `speed_test.py`, `backends/`). Adding a
  provider means adding one module.
- **The user chooses the backend:** Cloudflare, M-Lab NDT7 or
  LibreSpeed, or none (the default).
- **IHM runs its own tests.** No backend reads another HA integration's
  sensors.
- **Bufferbloat included:** the latency increase under load per
  direction, and a grade of the larger on Waveform's scale (R3; ADR-004
  amendment), complementing ADR-001's passive signal.
- **No server to run,** by the user or Solent Labs.
- **When tests run:** automatic tests, on by default once a service is
  chosen, at a random time from 1 to 5 am local; plus the Run speed test
  button and automations that press it. The schedule is IHM's, not the
  user's: HA's `appropriate-polling` rule (R16) bars a user-set
  interval, so automatic tests are only on or off. IHM derives the
  spacing from the data budget: weekly with none, else as often as the
  budget holds every test at its limit (SPEED_TEST_BACKENDS.md § Data
  Use). Other times go through an automation. Overnight, a test is least
  likely to slow a call or a game; random, homes don't all test at once
  (R9). No test runs at startup.
- **Whole tests over frequent ones.** A test the data limit cuts short
  measures less well, so the data limit defaults to automatic: each
  direction gets 10 s at the last test's speed plus 25%, within the
  budget. Each throughput reading says whether time or the limit ended
  it. The setup screen shows the working.
- **No busy-line check.** The FCC's units skip a test while household
  traffic passes 200 kbps (R21), but they sit between modem and router;
  IHM on the HA host cannot see other devices' traffic, so it does not
  guess.
- **Three limits bound the cost,** counting every run, failed ones
  included: a data limit per test (default automatic; one set by hand
  stops each direction at half), a daily test limit (default 4, up to
  40), and an optional data budget per 30 days. A test starts only if
  its data limit fits what is left of the budget, so the budget is never
  exceeded. Setup advises keeping the budget to a small share of any
  plan cap (R22).
- **A failed test is visible:** the sensors go unavailable and the
  button gives the reason; nothing reads 0. A failure still reports the
  data it moved.
- **Our own clients.** A library that meets IHM's rules is reused, one
  with gaps is patched upstream, and otherwise IHM writes its own, which
  must beat the alternatives on measurable terms. None qualified:
  `fastdotcom` blocks, returns 0 on failure and sets no User-Agent
  (R19); no Python NDT7 client exists (R9); `cloudflarepycli` is
  GPL-3.0 (R5).

**Constraints:**

- **Keep to each provider's terms as closely as possible;** this is part
  of what IHM offers. Where terms are silent, use the provider as its
  own published client does, identify honestly, and stay modest.
- A backend may use a public endpoint without written permission
  (other HA integrations do: R8), provided the provider's published
  limits apply, requests identify IHM (User-Agent or client name), and
  the docs state IHM is not affiliated.
- **M-Lab:** the user consents before first use, since M-Lab publishes
  results with the user's IP address; a run no person started (an
  automatic test included) counts toward at most 4 a day; one an
  automation started waits a random time of up to an hour (R9).
- **Not offered:** Fast.com, because Netflix's Terms of Use forbid "any
  robot, spider, scraper or other automated means to access the Netflix
  service" and include "our websites" in it, while every client must
  read a token from fast.com's page (R19); Ookla, whose CLI needs a
  personal, non-commercial license accepted on the user's behalf (R8).
  Written permission from a provider would reopen it.
- No backend accepts a license or terms for the user, and client
  libraries must have a license compatible with distribution.

---

## ADR-004: No composite health sensors

**Status:** Accepted 2026-11-18

**Question:** Keep the planned 0-100 `connection_quality` sensor and the
`connection_healthy` composite binary sensor (then planned in the ROADMAP)?

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
state, or a grade under the amendment below. `gateway_reachable` and
`internet_reachable` stay: each reports one directly observed state.

**Amendment: grades on a published scale** (Open, 2026-11-20; awaits
the developer's Accept). A grade that reads one measured quantity
against a published, cited scale is a reading, not a composite: it
hides no signal and invents no cutoff. Allowed when:

- the input is one measured quantity, with its own entities, so the
  grade never hides what moved;
- the scale is the source's, cited in REFERENCES.md with a [V] label,
  never IHM's own;
- the grade follows the source's own rule for choosing the input.

First use: the speed test bufferbloat grade, Waveform's scale applied
to the larger latency increase under load, as Waveform grades (R3); the
download and upload increases are sensors of their own.
hass-speedtest-ookla's grade uses a scale of its own above B (R8); IHM
keeps to the source's.

---

## ADR-005: Core runs anywhere

**Status:** Accepted 2026-11-18

**Decision:** The measurement core is a standalone Python package under
the Solent Labs namespace, following Cable Modem Monitor's packaging
(`solentlabs.cable_modem_monitor_core`): `solentlabs.internet_health_monitor_core`,
published to PyPI as `solentlabs-internet-health-monitor-core`. The
integration's `manifest.json` pins its version, as CMM's does, so each
release publishes Core to PyPI before the integration (ROADMAP § Path to
Release). It can run outside Home
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

**Platforms (decided 2026-11-19):** Linux and Windows. Only the probes
differ by OS (gateway, system DNS, ping, trace, host environment); they
sit behind one `Platform` interface in `core/platforms/`, and
`get_platform()` picks the module. Linux runs `ip`, `ping` and
`traceroute`. Windows calls the IP Helper API directly (R13), so it
parses no text and works in any display language, without admin rights.
Windows reports round-trip times in whole milliseconds (R13); a
sub-millisecond gateway reads 0 or 1 ms there. Any other OS raises
`UnsupportedPlatformError`.

macOS is not built: no demand yet and no Mac to capture test data on.
Adding it is one module implementing `Platform`, one branch in
`get_platform()`, and tests from captured macOS output.

---

## ADR-006: Outside services only by user choice

**Status:** Accepted 2026-11-19

**Context:** Hop enrichment sent each public hop IP to ip-api.com over
plain HTTP and the gateway's MAC address to api.macvendors.com, always
on and undisclosed. Neither is a measurement, and both told a third
party about the user's network. Both were removed.

**Decision (rule, 2026-11-19):** IHM may use an outside service only if
all of these hold:

1. **Off by default.** The user turns it on; nothing is sent until then.
2. **Transparent.** The option's own description names the service and
   what is sent, before the user enables it. README.md documents its
   benefits and limits.
3. **Listed.** `docs/ARCHITECTURE.md § Data Leaving the Host` has a row
   for it.
4. **Minimal.** It sends only what it needs; never the user's own
   address or device identifiers. The exception is a speed test: it is a
   connection from the user's network, so the provider
   always sees the user's public IP address. The option's description
   says so, and says which provider publishes it (M-Lab, which also
   requires the user's confirmation before its first use).
5. **Cited.** The provider's terms are in REFERENCES.md, and IHM keeps
   within them.

The probes themselves (ping, traceroute, the DNS query) and reverse DNS
through the host's own resolver are not outside services under this
rule. Current uses: speed test backends (ADR-003) and hop ownership
(below).

**Hop ownership** (decided 2026-11-19) is an opt-in option, off by
  default: each public hop's network operator (ASN and name) from Team
  Cymru's IP-to-ASN service over DNS (R15). The option's description
  says what is sent before the user enables it: public hop addresses
  (ISP routers, never the user's own address). Private and shared ISP
  addresses (10/8, 100.64/10, ...) have no owner and are never sent.
  Country is not used: Team Cymru says the service "should not be used
  for IP geolocation" (R15). Chosen over a bundled IP-to-ASN database,
  which would add several MB and age between releases. Limits, stated
  to users in README.md § Hop Ownership: many home paths have no public
  address in the first three hops, so the option often finds nothing;
  a router at a handoff between networks can carry the other network's
  address.

**Constraints:** Every new outside service meets the rule above and is
recorded here or in its own ADR.

---

## ADR-007: Fixed 60-second polling

**Status:** Accepted 2026-11-19

**Context:** IHM targets HA's Platinum quality scale. Its Bronze rule
`appropriate-polling`, and HA core's own guidance, say the developer sets
the interval and users do not get a field for it, in setup or options
(R16). IHM had a Scan Interval field; it was removed.

**Decision:** IHM polls every 60 seconds.

- **Comparable tools** use 30 to 60 s for "is it working now" monitoring:
  HA Ping 30 s, Uptime Kuma 60 s. SmokePing's 300 s
  suits long-term graphs, too slow for live sensors (R16).
- **60 over 30:** half the probes and database writes; an outage shows
  within a minute either way. Jitter is measured within each poll
  (ADR-009), so the interval does not change it.
- **Other intervals:** HA's documented route (polling off, an automation
  calling `homeassistant.update_entity`; README.md § Polling).

**Constraints:**

- Every interval, timeout and limit lives in Core's `timing.py`; the HA
  coordinator, the forms and the CLI read from it. No host defines its own.
- A regular poll's worst case (`steady_poll_bound_s`) must stay under
  `POLL_INTERVAL_S` at the maximum ping count; a test enforces it. The CLI
  refuses an `--interval` shorter than that bound for the chosen ping count.
- Passive bufferbloat (ADR-001) needs about one probe per second, which no
  poll interval provides; it gets its own cadence when it is built.

---

## ADR-008: Minimum Home Assistant 2026.10

**Status:** Accepted 2026-11-19

**Context:** IHM targets HA's Platinum quality scale, whose `strict-typing`
rule means the integration type-checks against the HA it runs on, with HA
core's mypy settings. HA 2026.9 replaced voluptuous with probatio; 2026.10
is the first release whose flow APIs are typed for probatio (R17). Code
cannot be strictly typed against both sides of that change without
compatibility imports and suppressed errors.

**Decision:** The minimum is HA 2026.10.0, and forms import `probatio`
directly, as HA core does (R17).

- IHM is unreleased, so no installed user is cut off; its `brand/` icon
  already needed HA 2026.3.
- HA's blog says custom integrations may keep `import voluptuous`; IHM
  does not, because strict typing and probatio's typed and translated
  validation need the direct import (R17). Cable Modem Monitor keeps
  voluptuous on a 2025.1 floor; this decision is IHM's alone (ADR-002).

**Constraints:**

- The floor is stated in `hacs.json`, `requirements-dev.txt` and
  `ha-minimum.txt`; a test fails if they disagree.
- `make setup` and the CI "minimum" job install with `ha-minimum.txt`;
  `make setup-current` and the "newest" job install the newest HA the test
  harness supports. Both run Python 3.14 and HA core's mypy settings
  (`pyproject.toml [tool.mypy]`).
- Core alone still supports Python 3.12 (its CLI); a CI job tests it there.
- Raising the floor again needs a reason recorded here.

---

## ADR-009: Jitter is consecutive delay variation

**Status:** Accepted 2026-11-19

**Context:** IHM reported jitter as the standard deviation of each poll's
mean latency over the last 30 polls. That is not a standard definition: it
measures drift across half an hour and averages away the packet-to-packet
variation that calls, games and streams suffer. RFC 3550's interarrival
jitter, RFC 5481's IPDV and Cloudflare's speed test all compare consecutive
samples (R18).

**Decision:** A target's jitter is the mean absolute difference between
consecutive round-trip times among one poll's pings (`consecutive_jitter`
in Core), as Cloudflare's speed test computes it (R18). It is the
unsmoothed form of RFC 3550's estimator, over round-trip rather than
one-way delay, since ping measures round trips.

**Constraints:**

- Jitter needs at least two replies in a poll; with one ping per target it
  is unknown. The default is three.
- No latency history is kept; each poll stands alone. HA's state history
  carries the trend for 10 days, and long-term statistics, when the user
  turns them on, carry it longer (ADR-013).
- Docs call it jitter (the term users know) and define it as above.

---

## ADR-010: Names are changed by renaming the device

**Status:** Accepted 2026-11-19

**Context:** A customizable entity name prefix was on the Local list, a
lesson from Cable Modem Monitor. HA core's integration guidance says "Do
NOT allow users to set config entry names in config flows. Names are
automatically generated or can be customized later in UI" (R16). IHM
targets Platinum.

**Decision:** No prefix setting. Entity names and ids start with the
device name, which defaults to "Internet Health" (`const.DEVICE_NAME`),
short enough for readable ids (`sensor.internet_health_hop_2_latency_isp`).
Users who want another prefix rename the device in HA, which offers to
rename the entity ids to match (README.md § Renaming).

**Constraints:**

- Docs use the default ids; `tests/components/test_docs.py` fails if an
  example names an id a new install does not create.
- The integration's own title stays "Internet Health Monitor"; only the
  device and entity names use the short form.

---

## ADR-011: Roadmap features not built

**Status:** Accepted 2026-11-19. The card reordering row was added
2026-11-20 and awaits the developer's Accept.

**Context:** The ROADMAP listed five "Future Considerations (Post-v1.0)".
The project does not defer work: each is built or cut with a reason.

**Decision:** None is built.

| Feature | Reason |
| --------- | -------- |
| IPv6 path | Not built until a user asks; ADR-014 keeps every IPv6 address out of the IPv4 path and names where IPv6 would be added |
| Custom hop targets | HA's own Ping integration pings any host the user adds, with latency, jitter and packet loss sensors (`homeassistant/components/ping/sensor.py`, HA 2026.10.4). IHM watches the path to the internet, not chosen hosts |
| Interface selection on multi-interface hosts | IHM follows the default route, the path the host's own internet traffic takes. Measuring another interface would report a path HA does not use |
| SNMP router counters | Reading the router is a different job from measuring the path, and needs a credential; IHM stores none. HA's SNMP integration exposes router counters as entities to combine with IHM's (as ADR-002 does with Cable Modem Monitor) |
| Solent Aggregator hook | ADR-002: combining happens in HA over entities, and any telemetry is a separate opt-in consumer. IHM owes an aggregator only its stable entity ids and units (ADR-001, ADR-002) |
| Reordering the dashboard card's sections in its form | HA's select selector has no reorder option (only the entity selector reorders, home-assistant.io/docs/blueprint/selectors, read 2026-11-20 [V]). A custom editor would be the card's first code CI cannot test, against the card's design as a thin layer over HA's own cards (DASHBOARD_CARD.md). `generate_dashboard_card` gives the card as YAML to reorder freely (README.md § Your Own Order or Layout) |

**Constraint:** Building any of these needs a use case in USE_CASES.md
and a new decision here.

---

## ADR-012: Reachability confirms before off and re-checks fast while off

**Status:** Accepted 2026-11-19

**Context:** Gateway reachable and Internet reachable changed only on the
60-second poll (ADR-007). Internet reachable rested on one DNS query, so
one lost UDP packet showed a false outage for a minute, and recovery took
up to a minute to show. Cable Modem Monitor runs a separate health probe
every 30 s by default (its `modem_health.py`); a constant faster probe
costs traffic all the time.

**Decision:** Check faster only while something is failing.

- While healthy, nothing runs between polls.
- A failed poll result does not turn a sensor off. Quick checks (one
  gateway ping, or one DNS query) follow 5 s apart; only if 2 more fail
  does it turn off. One answer keeps it on.
- While off, one quick check every 10 s; the first answer turns it back
  on. A successful poll also turns it on at once.
- A first poll that fails shows unknown until confirmed.

Core holds the logic (`reachability.py`) and the checks
(`NetworkDiagnostics.check_gateway`, `check_internet`); the host does the
scheduling (ADR-005). The counts are in `timing.py`.

**Consequences:** An outage shows within the poll interval plus about
10 s; recovery within about 10 s. Quick checks are counted in the usage
totals. During an outage the internet check costs one DNS query every
10 s.

**Constraint:** Nothing is added to the healthy path; a faster constant
cadence needs a new decision (ADR-001's passive bufferbloat probe would
be one).

---

## ADR-013: Long-term statistics only where they serve a use

**Status:** Open.

**Context:** Home Assistant keeps two kinds of history (R23). State
history records every change of every sensor and is purged after 10
days by default. Long-term statistics are hourly summaries, written only
for sensors with a `state_class`, and never purged. Cable Modem Monitor
measured what that costs: about 100 MB a year per modem, most of it from
per-channel sensors. An integration can choose `state_class`; it cannot
keep a sensor's state out of state history, which only the user's
`recorder: exclude` can.

**Decision:**

- **Usage totals carry no `state_class`.** The total is what matters, so
  they add nothing that is never purged. The README shows the
  `recorder: exclude` for users who want no state history either.
- **Measurement sensors carry one only by user choice.** A *Long-term
  statistics* option, off by default, sets `state_class: measurement` on
  hop latency, jitter and packet loss, DNS latency and the speed test
  readings. A before-and-after trend over months (UC-6) needs it; the
  10 days of state history serves the rest, and the card's graphs (at
  most 168 hours) never need it.

**Consequences:** Without `state_class`, the frontend still draws these
sensors as lines, since they have units (frontend `src/data/history.ts`).
Turning the option off after statistics exist makes HA raise one
"no longer has a state class" warning per sensor until the user deletes
its statistics (HA `sensor/recorder.py`); the option says so.

**Constraint:** A new sensor gets a `state_class` only under this
option, or with a use case that needs its statistics and a new
decision here.

---

## ADR-014: IPv4 path, ready for IPv6

**Status:** Open.

**Context:** IHM measures the IPv4 path (ADR-011). Hosts with IPv6 can
still hand it an IPv6 address: `/etc/resolv.conf` may name an IPv6
resolver, and IHM used to trace toward the DNS server whenever its
address did not start with an IPv4 private prefix, so such a host traced
IPv6 hops behind an IPv4 gateway. No user has asked for IPv6
monitoring.

**Decision:** IHM stays on the IPv4 path; IPv6 is built when a use case
asks for it (ADR-011's constraint). Until then:

- **One gate.** `PATH_IP_VERSION = 4` and `is_traceable()` in Core's
  `network_diagnostics.py` decide which address hops are traced toward:
  a public address of that version, else the default target. An IPv6
  address never enters the traced path.
- **Family-neutral where it costs nothing.** Address checks parse with
  `ipaddress`, which accepts both families (`platforms/base.py is_ip`);
  the DNS latency probe already queries an IPv6 resolver over IPv6
  (`dns_probe.py`); diagnostics redaction handles both (`redact.py`).
- **Where IPv6 would be added**, each IPv4-only today:
  1. Gateway: `ip route show default` lists IPv4 routes (`platforms/linux.py`);
     IPv6 needs `ip -6 route show default`.
  2. Windows probes: `IcmpSendEcho` takes an IPv4 address
     (`platforms/_iphlpapi.py`, R13).
  3. Default trace target: `DEFAULT_TRACE_TARGET` is an IPv4 address.
  4. Hop ownership: `origin_query_name()` looks up IPv4 only
     (`hop_owner.py`).
  5. Entities: a second set of hop sensors, with unique ids per family.
  6. Linux `ping` and `traceroute` take the address as given; their
     IPv6 behavior on each supported host needs checking before use.

**Constraint:** Code that takes an address accepts either family and
checks the family where it matters, through `PATH_IP_VERSION`; no new
IPv4-only parsing.
