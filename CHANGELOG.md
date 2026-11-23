# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-23

### Overview

The first release of Internet Health Monitor: latency, jitter and packet
loss along the path from Home Assistant to the internet (the gateway, the
next two hops and a reference address past your ISP), DNS latency,
reachability, and optional speed tests. Comparing the points shows
whether a problem starts at home, on your line or beyond it, including
bufferbloat past the router. Requires Home Assistant 2026.10.0 or later
on Linux (HA OS, Container, Supervised or Core) with `ip` and `ping`;
`traceroute` adds hops 2 and 3. Core, the measurement engine, is its own
package on PyPI (`solentlabs-internet-health-monitor-core`) and runs on
Linux and Windows with Python 3.12 or later. Betas 0.1.0b1 to 0.1.0b5
led here; each keeps its own notes on its GitHub pre-release.

### Added

- **Path sensors.** Latency, jitter and packet loss for hops 1 to 3 every
  60 seconds, with each hop's address and address type (private, shared
  ISP space or public). The gateway and hops are detected, and detected
  again when the gateway changes or a hop was missing. Jitter is the
  average change between consecutive round trips in a poll (RFC 3550, as
  Cloudflare's speed test measures it).
- **Internet reference.** The same three readings for an address past
  your ISP: Cloudflare's 1.1.1.1 by default; Google, Quad9, OpenDNS or a
  custom public IPv4 address; or off. The traceroute aims at it, so hops
  1 to 3 lie on the path to it.
- **DNS latency.** One uncached lookup per poll at your DNS server: on
  auto, the one the host uses (on HA OS and Supervised, the host's own
  server, which the Supervisor reports), or a provider or custom address
  you choose. Its attributes name the server and where it came from.
- **Gateway reachable and Internet reachable.** A failed check is
  confirmed by two quick re-checks before either turns off, and while off
  IHM re-checks every 10 seconds, so recovery shows within seconds.
  Nothing extra runs while everything answers.
- **Speed tests (off by default)** with Cloudflare, M-Lab NDT7 or
  LibreSpeed: download, upload, latency at rest and under load each way,
  and the data used, each throughput saying whether time or the data
  limit ended it. Automatic tests at a random time from 1 to 5 am, weekly
  or as often as the 30-day data budget holds every test; the Run speed
  test button, which asks first, and automations run them too, within a
  daily test limit. The data limit per test is automatic by default,
  sized from the last result for a whole test, and the setup screen shows
  its working. Each option says what the service sees; M-Lab asks for
  consent first because it publishes results with your IP address.
- **Bufferbloat:** the latency increase under load in each direction, and
  a grade from A+ to F on Waveform's published scale, shown on the card
  as gauges colored where Waveform says real-time use suffers.
- **Hop ownership (off by default):** the network operator of each public
  hop, from Team Cymru over DNS.
- **Usage totals:** pings, traceroutes, DNS queries, speed tests and their
  data, counted since install, always in the diagnostics download and as
  six optional sensors.
- **Long-term statistics (off by default)** for latency, jitter, packet
  loss, DNS latency and speed tests, for trends over months. They add
  about 10 to 15 MB to Home Assistant's database a year; the README's
  Database Space section gives the figures per option.
- **Connection type and Install type** diagnostic sensors.
- **Dashboard card:** pick Internet Health in Add card and set it up in a
  form, with a card per hop or one combined Network path card; the
  `generate_dashboard_card` action returns the same card as YAML.
- **Diagnostics download** with IHM's recent log records; hop hostnames
  and public IP addresses are redacted. The startup log line names the
  integration's version, the install type and the installed Core's.
- **Repair issue** when `traceroute` is missing, saying how to install it.
- **Command line:** `internet-health-monitor` prints each poll as a JSON
  line; `--speed-test` runs one speed test, keeping to M-Lab's limits for
  automated clients; `--internet-reference` picks the reference or turns
  it off.
- **Translations:** German, Spanish, French, Brazilian Portuguese and
  Simplified Chinese, plus English.
