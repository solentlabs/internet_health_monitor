# Architecture

How Internet Health Monitor (IHM) is put together, for someone reading
the code for the first time. Features and phases:
[ROADMAP.md](ROADMAP.md). Decisions: [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md).
Use cases: [USE_CASES.md](USE_CASES.md).

## What It Measures

IHM watches the path from the Home Assistant host to the internet:

```text
HA host ──> hop 1 (gateway) ──> hop 2 (ISP) ──> hop 3 (next router)
   ├──────────────────────────────────────────> internet reference
   └──────────────────────────────────────────> DNS server
```

For each hop it reports latency, jitter and packet loss, and its
`address_type` (private, shared or public, from the address itself:
[REFERENCES.md § R24](REFERENCES.md#r24-addresses-that-place-no-one));
for DNS, the
time to resolve a query. Comparing hops localizes a problem: hop 2
rising while hop 1 stays flat points past the router, which is how IHM
detects bufferbloat passively (ADR-001).

## Layers

Two layers, one-way dependency. Core is its own package (ADR-005), so
other hosts can use it; the command line is the second.

```text
HA layer  (custom_components/internet_health_monitor/*.py)    CLI (cli.py)
    config flow, coordinator, sensors,                    one JSON line
    binary sensors, buttons, diagnostics                  per poll
        │ calls run_diagnostics(), receives NetworkDiagnosticsResult │
        ▼                                                            ▼
Core      (packages/internet_health_monitor_core/, module
           solentlabs.internet_health_monitor_core, on PyPI as
           solentlabs-internet-health-monitor-core)
    network_diagnostics.py: polling, caching, jitter, loss, DNS, hostnames
    speed_test.py: one speed test interface and result (ADR-003)
    data_plan.py: a test's data limit and automatic tests' spacing
    bufferbloat.py: Waveform's grade (R3; ADR-004 amendment)
    mlab_runs.py: M-Lab's per-client limits for the command line
        backends/: _http.py (shared engine), cloudflare.py, librespeed.py, ndt7.py
    timing.py: every interval, timeout and limit (ADR-007)
        │ calls Platform: gateway, system DNS, ping, trace, host environment
        ▼
    platforms/  get_platform() picks: linux.py (ip, ping, traceroute)
                                      windows.py (IP Helper API)
        ▼
The network
```

`manifest.json` pins the Core version, and HA installs it from PyPI. In
development, `requirements-dev.txt` and the test container
(`scripts/dev/ha-entrypoint.sh`) install the local copy instead. Core
runs on Linux and Windows (ADR-005); Windows round-trip times are whole
milliseconds (REFERENCES.md § R13).

**Core** has no `homeassistant` import. `NetworkDiagnostics` takes a
`NetworkDiagnosticsConfig` and returns a `NetworkDiagnosticsResult`
(dataclasses). It holds the only state: cached gateway and hop IPs,
and hop hostnames. Each poll's measurements stand alone.

**HA layer** maps the result to entities and owns configuration and
scheduling. It contains no measurement logic.

| File | Role |
| ------ | ------ |
| `__init__.py` | Builds `NetworkDiagnostics` from the entry's options; with DNS server on auto under the Supervisor, passes the host's own DNS server (§ One Poll). Fails setup with a translated error on an unsupported OS or when `ip` or `ping` is missing; a failed first poll retries. Stores runtime data on `entry.runtime_data`. The options flow and Reconfigure reload the entry. |
| `coordinator.py` | `InternetHealthCoordinator` polls every `POLL_INTERVAL_S` (60 s, from Core's `timing.py`; ADR-007). `SpeedTestCoordinator` runs a speed test when the button is pressed and, with automatic tests on, overnight at the spacing Core's `data_plan.py` derives from the budget; sizes each test's data limit (automatic from the last result, or the user's); enforces the data limit, daily limit, 30-day data budget and M-Lab's automated-client rules; and stores each run's time and data, the last automatic test and the last result (HA storage `internet_health_monitor.speed_test`). Also the typed config entry and runtime data. |
| `entity.py` | `InternetHealthEntity`: unique id and the entry's single service device, shared by every entity. |
| `config_flow.py` | Setup and options, two screens: `build_schema` (DNS server, pings per target 1 to 10, internet reference, hop ownership, usage totals, speed test service), then, with a service chosen, `build_speed_test_schema` (automatic tests, data limit with 0 for automatic, daily test limit, data budget), with the working shown from the last result and a data limit no test could use refused; an M-Lab consent step. One entry per HA. |
| `sensor.py` | Per hop (1 to 3), and for the internet reference when set: latency, jitter, packet loss. Plus DNS latency and, with a service chosen, six speed test readings, `state_class: measurement` only with the Long-term statistics option on (ADR-013). Usage totals: no `state_class`, so no long-term statistics. Diagnostic enums: Connection type (Core's host environment) and Install type (HA's own `system_info`). |
| `binary_sensor.py` | `gateway_reachable` (gateway ping answered), `internet_reachable` (DNS query succeeded). |
| `button.py` | Refresh diagnostics; Reset network cache (disabled by default); Run speed test (with a service chosen; a press with no user counts as automated). A failed press raises a translated error. |
| `dashboard.py`, `services.py`, `card/` | Dashboard card: one layout builder behind the `generate_dashboard_card` action and the bundled Lovelace card; additive, so a card failure never stops monitoring ([DASHBOARD_CARD.md](DASHBOARD_CARD.md)). Registered once in `async_setup`. |
| `usage.py` | `UsageTracker`: running totals of pings, traceroutes, DNS queries and speed test runs and data. Adds Core's per-instance `NetworkDiagnostics.counts` to totals stored in HA storage (`internet_health_monitor.usage`), probe counts written within 5 minutes (a fixed deadline: HA's delayed save slides on every call) and on unload, speed test totals at once. |
| `diagnostics.py` | HA diagnostics download: options, poll state, the core's result, detection state, usage totals, speed test state and recent logs, redacted (§ Diagnostics). |
| `log_buffer.py` | `LogBuffer`: the newest 200 records from IHM's and Core's loggers, in memory, for the download. |
| `redact.py` | What the download leaves out (§ Diagnostics). |
| `strings.json`, `translations/`, `icons.json` | Every form label, entity name, error message and icon; no names or icons in code. |
| `quality_scale.yaml` | Self-assessment against HA's quality scale; .github/README.md § Quality Scale renders it. |

## One Poll

1. **First run only:** resolve the DNS server and note its source,
   which the DNS latency sensor and diagnostics report as `dns_source`:
   the chosen server (`chosen`); with auto under the Supervisor, the
   primary interface's first IPv4 nameserver from the Supervisor's
   network info (`host`), since `/etc/resolv.conf` inside HA names the
   Supervisor's own DNS relay; otherwise system `/etc/resolv.conf`
   (`system`), which may itself be a local relay such as Docker's
   127.0.0.11 or systemd-resolved's 127.0.0.53
   ([REFERENCES.md § R26](REFERENCES.md#r26-local-dns-relays)); fallback
   `1.1.1.1` (`fallback`). Pick the traceroute target: the internet
   reference when set (ADR-015), else the DNS server if it is a public
   IPv4 address, else `8.8.8.8` (ADR-014).
2. **Until cached:** detect the gateway (`ip route`), then hops 1 to 3
   (`traceroute -n -q 1 -w 2 -m 3 <target>`).
3. **Once, after hops are known:** look up each hop's hostname by
   reverse DNS and detect the host environment (container, connection
   type).
4. **Every poll, in parallel:** ping the gateway, ping each hop, ping
   the internet reference (a public IPv4 address, Cloudflare's 1.1.1.1
   by default, or none: ADR-015), query DNS. The DNS query is one UDP message Core builds itself (RFC 1035,
   [REFERENCES.md § R14](REFERENCES.md#r14-dns-message-format)), sent to the
   configured server for a random name (`_ihm-<random>.cloudflare.com`),
   so no cache can answer; latency is the time to its reply, NOERROR or
   NXDOMAIN, measured in-process. Same on every OS, no `dig` needed. Each target gets `ping_count` single pings (`ping -c 1`), run one
   after another.
5. Latency is the round-trip time `ping` itself reports, read from its
   min/avg/max summary line in both iputils and BusyBox formats. It is
   never timed from outside the process, which would add process start-up
   to every reading. Sources: RFC 2681, iputils `ping(8)` and HA core's
   ping integration ([REFERENCES.md § R10](REFERENCES.md#r10-ping-round-trip-time)).
   A hop's latency is the mean of its replies' round-trip times; loss is
   the share of pings with no reply. Jitter is the mean absolute
   difference between consecutive round-trip times within the poll
   (ADR-009, [REFERENCES.md § R18](REFERENCES.md#r18-jitter)). Core
   rounds latency, jitter and DNS latency to 0.001 ms and loss to
   0.1 % where it produces them, so float noise never reaches entities
   or diagnostics.

**Reachability between polls** (ADR-012): the binary sensors show a
confirmed state. A failed result starts quick checks (one gateway ping or
one DNS query, 5 s apart); three failures in a row turn the sensor off,
and while off a check runs every 10 s until one answers. Core
(`reachability.py`) decides; the coordinator schedules. Nothing runs
between polls while everything answers.

**Failure isolation:** the three checks run under `asyncio.gather` with
`return_exceptions=True`, so one failing check yields an unreachable or
empty result for that check only. The reset buttons clear the caches,
so detection runs again on the next poll.

**Container networking:** IHM sees the path from its own network
namespace. Under Docker Desktop (the local test setup), hop 1 is the
Docker bridge and nothing beyond it answers traceroute; ICMP traceroute
reaches the destination at the next hop, so the router and ISP hops are
never visible (observed 2026-11-18). Hops 2 and 3 need HA on the real
network: HA OS, a bridged VM, or a container with host networking on a
Linux host.

## Data Leaving the Host

Beyond the probes themselves (ping, traceroute and the DNS query), IHM
sends only:

| Destination | What is sent | When |
| ------------- | -------------- | ------ |
| The host's configured DNS resolver | Each hop IP, as a reverse DNS query | Once after hops are detected, and after a cache reset |
| Team Cymru, through the DNS server under test | Each public hop IP, as an `origin.asn.cymru.com` query, then its ASN | Only with Hop ownership on (off by default); same timing as reverse DNS |
| Cloudflare (speed.cloudflare.com) | Test data both ways; it sees the public IP address. Nothing is posted to its results endpoint | Each speed test, with Cloudflare chosen |
| M-Lab (Locate API, then an M-Lab server) | Client name and version; test data both ways. **M-Lab publishes the result with the public IP address** | Each speed test, with M-Lab chosen and consent given |
| LibreSpeed (librespeed.org server list, then volunteer servers) | One small request to each listed server to choose one; test data both ways with that one. No telemetry | Each speed test, with LibreSpeed chosen |

Nothing else goes to an outside service; any that is added is opt-in and listed here (ADR-006). Every speed test request carries the User-Agent `internet-health-monitor/<version>`.

## Diagnostics

HA's diagnostics download is what a user attaches to a bug report, so it
carries IHM's recent log records: HA OS keeps no log file a user can
attach, and HA's system log holds only warnings and errors.

- **Logs:** `log_buffer.py` keeps the newest 200 records from the
  integration's and Core's loggers in memory from HA start, at whatever
  level HA's logger settings allow (INFO by default; everything with
  debug logging on). IHM never changes a logger's level.
- **Redacted** (HA asks that location and personal data stay out,
  [REFERENCES.md § R24](REFERENCES.md#r24-addresses-that-place-no-one)):
  hop hostnames, by key; and every public address, wherever it appears,
  logs included. Kept: private, shared (CGNAT), loopback and link-local
  ranges, and the public resolvers IHM offers. A hop's network (ASN and
  owner) stays, so the ISP is still known.
- **Never logged:** a hop's hostname. The diagnostics redact it by key,
  and the log line that found it names only the address.

## Security

Reviewed 2026-11-19 (ROADMAP Phase 5); `packages/internet_health_monitor_core/tests/test_security.py` holds each guarantee.

- **No shell, no option injection.** Linux probes run `ip`, `ping` and
  `traceroute` with `create_subprocess_exec` (an argument list, never a
  shell). The only outside value in those arguments is the target, and
  `ping` and `trace` refuse anything that does not parse as an IP
  address, so text from tool output, `/etc/resolv.conf`, stored options
  or `--dns-server` can never become an option. The parsers keep only
  addresses as well. Windows calls the IP Helper API directly; no
  command line exists.
- **Provider-supplied URLs need TLS.** LibreSpeed's server list and
  M-Lab's Locate reply name the hosts a test loads. IHM uses only
  `https://` and `wss://` URLs from them, with certificate checks, and
  follows no redirects, so a tampered list or a server cannot aim test
  traffic at a device on the LAN.
- **Nothing secret is held.** IHM stores no credentials. The public IP
  address is never read or stored; the diagnostics download is redacted
  (§ Diagnostics).
- **The card renders no HTML from data.** Messages are set with
  `textContent`; the layout is built by HA's own card helpers.

## Neighbors

No code dependency in either direction (ADR-002).

| Integration | Measures | Boundary |
| ------------- | ---------- | ---------- |
| Cable Modem Monitor | DOCSIS signal, errors, modem ping | Combined with IHM in HA templates over entities (UC-7). |
| Other speed test integrations | Throughput | IHM does not read them (ADR-003). |

What makes combining possible is stable entity ids and ms units.
