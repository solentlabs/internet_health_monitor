# Architecture

How Internet Health Monitor (IHM) is put together, for someone reading
the code for the first time. Features and phases:
[ROADMAP.md](ROADMAP.md). Decisions: [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md).
Use cases: [USE_CASES.md](USE_CASES.md).

## What It Measures

IHM watches the path from the Home Assistant host to the internet:

```
HA host ──> hop 1 (gateway) ──> hop 2 (ISP) ──> hop 3 (backbone)
   └──────────────────────────────────────────> DNS server
```

For each hop it reports latency, jitter and packet loss; for DNS, the
time to resolve a query. Comparing hops localizes a problem: hop 2
rising while hop 1 stays flat points past the router, which is how IHM
detects bufferbloat passively (ADR-001).

## Layers

Two layers, one-way dependency. Core is its own package (ADR-005), so
other hosts can use it; the command line is the second.

```
HA layer  (custom_components/internet_health_monitor/*.py)    CLI (cli.py)
    config flow, coordinator, sensors,                    one JSON line
    binary sensors, buttons, diagnostics                  per poll
        │ calls run_diagnostics(), receives NetworkDiagnosticsResult │
        ▼                                                            ▼
Core      (packages/internet_health_monitor_core/, module
           solentlabs.internet_health_monitor_core, on PyPI as
           solentlabs-internet-health-monitor-core)
    network_diagnostics.py: polling, caching, jitter, loss, DNS, hostnames
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
hop hostnames, and a rolling latency history per hop (last 30 polls) for
jitter.

**HA layer** maps the result to entities and owns configuration and
scheduling. It contains no measurement logic.

| File | Role |
|------|------|
| `__init__.py` | Builds `NetworkDiagnostics` from the entry's options. Fails setup with a translated error on an unsupported OS or when `ip` or `ping` is missing; a failed first poll retries. Stores runtime data on `entry.runtime_data`; reloads when options change. |
| `coordinator.py` | `InternetHealthCoordinator` polls every 60 s (fixed; HA quality scale `appropriate-polling`), and the typed config entry and runtime data. |
| `entity.py` | `InternetHealthEntity`: unique id and the entry's single service device, shared by every entity. |
| `config_flow.py` | Setup and options from one `build_schema`: gateway and DNS monitoring, DNS server, pings per target (1 to 10), hop ownership. One entry per HA. |
| `sensor.py` | Per hop (1 to 3): latency, jitter, packet loss. Plus DNS latency. All `state_class: measurement`. |
| `binary_sensor.py` | `gateway_reachable` (gateway ping answered), `internet_reachable` (DNS query succeeded). |
| `button.py` | Refresh diagnostics; Reset network cache (disabled by default). A press whose poll fails raises a translated error. |
| `diagnostics.py` | HA diagnostics download: options, poll state, the core's result and detection state. |
| `strings.json`, `translations/`, `icons.json` | Every form label, entity name, error message and icon; no names or icons in code. |
| `quality_scale.yaml` | Self-assessment against HA's quality scale; README.md § Quality Scale renders it. |

## One Poll

1. **First run only:** resolve the DNS server (system `/etc/resolv.conf`
   when set to auto, else the chosen server; fallback `1.1.1.1`). Pick
   the traceroute target: the DNS server if public, else `8.8.8.8`.
2. **Until cached:** detect the gateway (`ip route`), then hops 1 to 3
   (`traceroute -n -q 1 -w 2 -m 3 <target>`).
3. **Once, after hops are known:** look up each hop's hostname by
   reverse DNS and detect the host environment (container, connection
   type, install type).
4. **Every poll, in parallel:** ping the gateway, ping each hop, query
   DNS. The DNS query is one UDP message Core builds itself (RFC 1035,
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
   the share of pings with no reply. Jitter is the standard deviation of
   the per-poll mean latency over the rolling history.

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
|-------------|--------------|------|
| The host's configured DNS resolver | Each hop IP, as a reverse DNS query | Once after hops are detected, and after a cache reset |
| Team Cymru, through the DNS server under test | Each public hop IP, as an `origin.asn.cymru.com` query, then its ASN | Only with Hop ownership on (off by default); same timing as reverse DNS |

Nothing else goes to an outside service; any that is added is opt-in and listed here (ADR-006). Speed test backends, when built and
enabled, are the only addition (ADR-003).

## Planned Components

Not built yet; designs are fixed by the ADRs named.

**Speed test backends** (ADR-003). Optional, off by default.

```
HA layer: schedule, run-now button, speed test sensors
        │
        ▼   (in Core)
bandwidth.py ── one interface: run a test, return download,
        │            upload, idle and loaded latency per direction
        ▼
backends/  ndt7.py (first) · cloudflare.py · fastcom.py · librespeed.py
```

A backend is one module implementing that interface. Adding a provider
touches nothing outside its module and its registration. Comparison:
[SPEED_TEST_BACKENDS.md](SPEED_TEST_BACKENDS.md).

**Dashboard card** (ROADMAP Phase 2). A bundled Lovelace card in the
Add card list, following Cable Modem Monitor's card pattern. Additive:
if it fails to load, monitoring is unaffected.

## Neighbours

No code dependency in either direction (ADR-002).

| Integration | Measures | Boundary |
|-------------|----------|----------|
| Cable Modem Monitor | DOCSIS signal, errors, modem ping | Combined with IHM in HA templates over entities (UC-7). |
| Other speed test integrations | Throughput | IHM does not read them (ADR-003). |

What makes combining possible is stable entity ids and ms units.
