# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Windows support for Core.** The measurement engine runs on Windows as
  well as Linux, through Windows' own network functions, so it works in any
  display language without admin rights. Windows round-trip times are whole
  milliseconds.
- **Command line.** `internet-health-monitor` runs one poll and prints the
  result as JSON; `--interval` keeps polling, one JSON line per poll.
- **Integration icon.** A sonar ping: a green home node and three arcs for
  the three hops, with a light-mode and a dark-mode version. Ships in `brand/`, which Home Assistant
  2026.3 and later shows without a brands-repo submission.

### Changed

- **Core is its own package**, `solentlabs-internet-health-monitor-core`
  (module `solentlabs.internet_health_monitor_core`), so it can run outside
  Home Assistant. The integration requires it; HA installs it from PyPI.
- **No more third-party lookups.** Hop IPs are no longer sent to ip-api.com
  and the gateway's MAC address is no longer sent to macvendors.com, so the
  hop ISP, ASN, location and MAC vendor attributes are gone. Hostnames still
  come from reverse DNS.
- **Removed the Refresh Network Info button.** Reset Network Cache also
  re-reads hostnames.
- **Tests run on the oldest and newest supported Home Assistant.**
  `make test` uses Python 3.12 (HA 2025.1.x), `make test-current` Python 3.14
  (newest HA), and CI runs both. Development dependencies are listed only in
  `requirements-dev.txt`.
- **Home Assistant 2025.1.0 is now the minimum**, so the options flow can
  rely on HA providing `config_entry`.

### Fixed

- **DNS latency is accurate everywhere.** Core sends its own uncached query
  to the chosen DNS server instead of running `dig`. Without `dig` (all of
  Windows, and Linux hosts without it), the old fallback timed the system's
  own lookup, which could answer from a local cache.

- **Options open on current Home Assistant.** Opening options failed with
  `AttributeError: property 'config_entry' ... has no setter` because the
  flow set `config_entry` itself, which HA stopped allowing after 2025.12.

- **Latency is the round-trip time ping reports.** It was the wall-clock
  time to start and finish the `ping` process, which added process
  start-up to every reading and could swamp a 1 ms gateway round trip.
  Both iputils and BusyBox output are read. A reply whose output has no
  round-trip time still counts as received for packet loss.

## [0.1.0] - 2025-12-XX

### Added

- **Command line.** `internet-health-monitor` runs one poll and prints the
  result as JSON; `--interval` keeps polling, one JSON line per poll.
- **Initial Release** - Internet Health Monitor for Home Assistant

#### Sensors
- **Gateway Latency** - Round-trip time to your router/modem (ms)
- **Gateway Jitter** - Standard deviation of recent latency measurements (ms)
- **Packet Loss** - Percentage of dropped packets to gateway (%)
- **ISP Latency** - Round-trip time to ISP's first hop router (ms)
- **DNS Latency** - Time to resolve DNS queries (ms)

#### Binary Sensors
- **Gateway Reachable** - Connectivity status to local gateway
- **Internet Reachable** - DNS resolution success indicator

#### Buttons
- **Refresh Diagnostics** - Trigger immediate network check
- **Reset Network Cache** - Clear cached gateway/ISP hop detection

#### Configuration
- **Zero-config setup** - Auto-detects gateway via `ip route`
- **Auto DNS detection** - Reads system DNS from `/etc/resolv.conf`
- **Configurable scan interval** - 10-3600 seconds (default: 60)
- **Configurable ping count** - 1-10 pings per check (default: 3)
- **DNS server selection** - Auto, Cloudflare, Google, Quad9, OpenDNS

#### Infrastructure
- **HA Diagnostics** - Download diagnostics for troubleshooting
- **Multi-language support** - English, German, Spanish, French, Portuguese (BR)
- **Modern HA patterns** - SensorEntityDescription, CoordinatorEntity
- **Full test coverage** - Unit and integration tests

#### Technical Details
- **Gateway detection** - Uses `ip route show default` on Linux
- **ISP hop detection** - Uses `traceroute` to find first external hop
- **DNS timing** - Uses `dig` for accurate measurement, falls back to socket
- **Jitter calculation** - Rolling standard deviation of last 30 measurements

### Requirements
- Home Assistant 2024.1.0+
- Python 3.12+
- Linux host (for gateway detection)
- Optional: `traceroute` for ISP latency
- Optional: `dig` for accurate DNS latency

---

**Part of the Solent Labs Network Suite**
- [Cable Modem Monitor](https://github.com/solentlabs/cable_modem_monitor) - Monitor cable modem signal quality
- [Internet Health Monitor](https://github.com/solentlabs/internet-health-monitor) - Track network latency and health
