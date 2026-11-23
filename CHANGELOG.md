# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **DNS latency on HA OS timed the Supervisor's relay.** Auto-detect
  picked 172.30.32.3, a relay inside Home Assistant, not your DNS
  server. On HA OS and Supervised it now times the host's own DNS
  server, which the Supervisor reports.

### Added

- **Internet reference.** A fourth ping target past your ISP, on by
  default: Cloudflare's 1.1.1.1. It reports latency, jitter and packet
  loss like a hop, in its own sensors, card and graph lines, so a
  slowdown can be placed at home, on your line, or beyond it. Pick
  another provider, type a public IPv4 address, or turn it off. The
  traceroute now aims at it.
- **Where the DNS server came from.** The DNS latency sensor and the
  diagnostics download report `dns_source`: chosen, host, system or
  fallback.

### Removed

- **"Monitor gateway and hops" and "Monitor DNS" options.** Nothing
  needed them, and they made the setup form longer. The gateway, hops
  and DNS are always measured; the internet reference is the one probe
  you can turn off.

### Changed

- **Hop 3 is no longer called "backbone".** It is the router after your
  ISP's first one, often still inside your ISP. Its sensors are now
  "Hop 3 latency", "Hop 3 jitter" and "Hop 3 packet loss"; existing
  entity ids are kept.
- **Each hop reports its address type** (`address_type`: private,
  shared or public, from the address itself) in place of
  `typical_location`, which guessed from the hop's position.
- **Rounded measurements.** Latency, jitter and DNS latency are
  reported to 0.001 ms and packet loss to 0.1 %, so long float tails
  no longer appear in attributes or diagnostics.

## [0.1.0b2] - 2026-11-20

### Fixed

- **Bufferbloat gauges before the first speed test.** The card showed
  "non-numeric" warnings in place of the three gauges until a test had
  run. Each gauge now appears once its value is measured.
- **Bufferbloat gauges looked alarming on a good line.** They ran to
  500 ms, so 88% of each arc was red past grade B. They now run to
  100 ms: green up to B fills 60%. A larger value pins the needle at
  the end, and the grade letter and the ms stay exact.
- **A double click ran two speed tests.** A press while a test runs is
  now ignored, and uses none of the daily or data allowance.
- **Usage totals flooded the logbook.** Pings, traceroutes, DNS queries
  and speed tests had no unit, so Home Assistant's logbook recorded each
  count's change every minute. Each now has a unit (pings, traceroutes,
  queries, tests), which the logbook leaves out.

### Added

- **Run speed test asks first.** The card shows it as its own button,
  which asks before a test fills your connection.
- **A notification with the result** when you press Run speed test
  yourself: download, upload and the bufferbloat grade, or why the test
  failed. Automatic tests and automations stay silent.
- **Your own DNS server.** Type any IPv4 or IPv6 address, such as a
  Pi-hole's, in place of the listed servers.
- **Hop addresses on the card.** Each hop's card shows its IP address.

### Changed

- **Made by Solent Labs.** The Marketplace and HACS list the integration
  under solentlabs alone (`manifest.json` code owners).
- **README.** Two, as Cable Modem Monitor has: a short one for the
  Marketplace listing, and the full one on GitHub (`.github/README.md`),
  with badges, a dashboard screenshot, installing from
  the Marketplace or HACS and testing a beta (replacing the manual copy),
  and where to get support.

### Security

- **CodeQL** scans the Python and the card's JavaScript on every push and
  pull request to `main`, and weekly.

## [0.1.0b1] - 2026-11-20

### Overview

The first release of Internet Health Monitor: latency, jitter and packet
loss along the path from Home Assistant to the internet (the gateway and
the next two hops), DNS latency, reachability, and optional speed tests.
Comparing hops shows where a problem starts, including bufferbloat past
the router. Requires Home Assistant 2026.10.0 or later on Linux (HA OS,
Container, Supervised or Core) with `ip` and `ping`; `traceroute` adds
hops 2 and 3. Core, the measurement engine, is its own package on PyPI
(`solentlabs-internet-health-monitor-core`) and runs on Linux and Windows
with Python 3.12 or later.

### Added

- **Path sensors.** Latency, jitter and packet loss for hops 1 to 3, and
  DNS latency, every 60 seconds. The gateway, hops and system DNS are
  detected, and detected again when the gateway changes or a hop was
  missing. Jitter is the average change between consecutive round trips
  in a poll (RFC 3550, as Cloudflare's speed test measures it).
- **Gateway reachable and Internet reachable.** A failed check is
  confirmed by two quick re-checks before either turns off, and while off
  IHM re-checks every 10 seconds, so recovery shows within seconds.
  Nothing extra runs while everything answers.
- **Speed tests (off by default)** with Cloudflare, M-Lab NDT7 or
  LibreSpeed: download, upload, latency at rest and under load each way,
  and the data used, each throughput saying whether time or the data
  limit ended it. Automatic tests at a random time from 1 to 5 am, weekly
  or as often as the 30-day data budget holds every test; the Run speed
  test button and automations run them too, within a daily test limit.
  The data limit per test is automatic by default, sized from the last
  result for a whole test, and the setup screen shows its working. Each
  option says what the service sees; M-Lab asks for consent first because
  it publishes results with your IP address.
- **Bufferbloat:** the latency increase under load in each direction, and
  a grade from A+ to F on Waveform's published scale. The card shows them
  as gauges, the grade's letter and each direction in ms, colored where
  Waveform says real-time use suffers.
- **Hop ownership (off by default):** the network operator of each public
  hop, from Team Cymru over DNS.
- **Usage totals:** pings, traceroutes, DNS queries, speed tests and their
  data, counted since install, always in the diagnostics download and as
  six optional sensors.
- **Long-term statistics (off by default)** for latency, jitter, packet
  loss, DNS latency and speed tests, for trends over months.
- **Connection type and Install type** diagnostic sensors.
- **Dashboard card:** pick Internet Health in Add card and set it up in a
  form; the `generate_dashboard_card` action returns the same card as
  YAML.
- **Diagnostics download** with IHM's recent log records; hop hostnames
  and public IP addresses are redacted.
- **Repair issue** when `traceroute` is missing, saying how to install it.
- **Command line:** `internet-health-monitor` prints each poll as a JSON
  line; `--speed-test` runs one speed test, keeping to M-Lab's limits for
  automated clients.
- **Translations:** German, Spanish, French, Brazilian Portuguese and
  Simplified Chinese, plus English.
