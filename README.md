# Internet Health Monitor

[![Solent Networks Suite](https://img.shields.io/badge/Solent%20Networks-Suite-blue)](https://github.com/solentlabs)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A **Solent Labs** Home Assistant integration for comprehensive internet health monitoring with multi-hop network path visibility.

Part of the **Solent Networks Suite** - tools for comprehensive home network visibility.

## Features

- **Network path, hop by hop** - Latency, jitter and packet loss for hop 1 (your gateway), hop 2 (usually your ISP's first router) and hop 3, so you can see where a problem starts
- **DNS latency** - One uncached lookup per poll at the DNS server you choose
- **Reachability** - Gateway reachable and internet reachable binary sensors
- **Zero configuration** - Gateway, hops and DNS server are detected automatically

### What Makes This Different

| Feature | Other Solutions | Internet Health Monitor |
|---------|-----------------|------------------------|
| Gateway detection | Manual config | Auto-detected |
| Path visibility | Single target only | Hops 1 to 3, each with its own sensors |
| DNS latency | Cache-affected | Uncached query to your chosen DNS server |
| Configuration | YAML editing | UI setup |

## Installation

### Manual Installation

1. Copy `custom_components/internet_health_monitor` to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration
4. Search for "Internet Health Monitor"

### HACS (Coming Soon)

This integration will be available through HACS once publicly released.

### Removal

1. Go to Settings > Devices & Services > Internet Health Monitor
2. Open the menu (three dots) and select Delete
3. For a manual install, delete `config/custom_components/internet_health_monitor` and restart Home Assistant

## Configuration

During setup, and later under Configure, you can set:

| Option | Default | Description |
|--------|---------|-------------|
| Monitor gateway and hops | on | Latency, jitter and packet loss for the gateway and hops 1 to 3 |
| Monitor DNS | on | Time one uncached lookup per poll |
| DNS server | Auto-detect | Server to time; auto-detect uses the one this host is configured with |
| Pings per target | 3 | Pings sent to each target per poll (1 to 10) |
| Look up who runs each hop | off | Adds each public hop's network operator; sends hop addresses to Team Cymru. See [Hop Ownership](#hop-ownership) |

### Polling

IHM polls every 60 seconds, in line with comparable monitors
([ADR-007](docs/ARCHITECTURE_DECISIONS.md#adr-007-fixed-60-second-polling)). For a different interval, open the integration's
System options, turn off "Enable polling for changes", and call
`homeassistant.update_entity` from an automation:

```yaml
automation:
  - alias: Poll Internet Health Monitor every 5 minutes
    triggers:
      - trigger: time_pattern
        minutes: "/5"
    actions:
      - action: homeassistant.update_entity
        target:
          entity_id: sensor.internet_health_monitor_dns_latency
```

Updating any one IHM entity runs a full poll for all of them.

### Hop Ownership

Off by default. When on, each hop sensor gains `asn` and `as_name`
attributes naming the network that runs that hop, for example
`15169` / `GOOGLE - Google LLC, US`.

| | |
|---|---|
| **What you get** | Whose network a hop belongs to: useful evidence when you report a problem to your ISP, and it works when a router has no hostname. |
| **What is sent** | Each public hop address to Team Cymru's free IP-to-ASN service, as a DNS query through your DNS server. These are your ISP's routers, never your own address. Looked up once when hops are detected, not every poll. |
| **What it often can't do** | Many ISPs use private (`10.x`) or shared (`100.64.x`) addresses on their first routers. Those have no owner, are never sent, and show no `asn`. On such a connection the option finds nothing in hops 1 to 3. |
| **Accuracy** | A router where two networks meet may carry the other network's address, so it can be labelled with the neighbouring operator. |
| **Not included** | Location. IP location data is unreliable for routers, and Team Cymru asks that the service not be used for it. Router hostnames often name the city anyway. |

## Entities

### Sensors

Three per hop, for hops 1 (gateway), 2 (ISP) and 3 (backbone), plus DNS:

| Sensor | Unit | Description |
|--------|------|-------------|
| Hop N latency | ms | Average round-trip time ping reported for this hop |
| Hop N jitter | ms | Standard deviation of this hop's latency over the last 30 polls |
| Hop N packet loss | % | Share of this poll's pings to the hop with no reply |
| DNS latency | ms | Time for one uncached lookup at the DNS server |

Hop sensors carry attributes: `hop_ip`, `reachable`, `packets_sent`,
`packets_received`, `hostname` (when the hop has one) and, with hop
ownership on, `asn` and `as_name`. All sensors keep long-term statistics.

### Binary Sensors

| Sensor | On when |
|--------|---------|
| Gateway reachable | The gateway answered a ping in the latest poll |
| Internet reachable | The DNS lookup succeeded in the latest poll |

### Buttons

| Button | Description |
|--------|-------------|
| Refresh diagnostics | Poll now instead of waiting for the next poll |
| Reset network cache | Forget the detected gateway, hops and hostnames and detect them again. Disabled by default; enable it when troubleshooting |

## Speed Testing (Planned)

Optional, and off until you turn it on. You choose which service runs
the test; every backend that supports it also reports bufferbloat
(latency while the line is loaded).

| Backend | Bufferbloat reading | Your results made public? | Limits |
|---------|---------------------|---------------------------|--------|
| Cloudflare | Yes, per direction | No (anonymised) | Modest default schedule |
| M-Lab NDT7 | Approximate, best for download | **Yes, including your IP address** | About 4 tests a day |
| Fast.com | To be confirmed | No (aggregates only) | Modest default schedule |
| LibreSpeed | No (idle ping only) | No | Modest default schedule |

Ookla is not offered: its licence is personal, non-commercial use only.
IHM is not affiliated with any of these providers. Full comparison:
[docs/SPEED_TEST_BACKENDS.md](docs/SPEED_TEST_BACKENDS.md).

## Network Path Visualization

```
[HA Host] ─Hop 1─> [Gateway] ─Hop 2─> [ISP Router] ─Hop 3─> [Backbone] ─DNS─> [DNS Server]
           1.2ms      │         15ms       │          25ms      │        35ms
                      └── Packet Loss ─────┴── Jitter ──────────┘
```

## Dashboard Examples

Entity ids below are the ones a new install creates. More examples:
[docs/dashboard-examples.md](docs/dashboard-examples.md).

### Network Path at a Glance

```yaml
type: glance
title: Network Path
entities:
  - entity: sensor.internet_health_monitor_hop_1_latency_gateway
    name: Gateway
  - entity: sensor.internet_health_monitor_hop_2_latency_isp
    name: ISP
  - entity: sensor.internet_health_monitor_hop_3_latency_backbone
    name: Backbone
  - entity: sensor.internet_health_monitor_dns_latency
    name: DNS
```

### Latency History

```yaml
type: history-graph
title: Network Path Latency (24h)
hours_to_show: 24
entities:
  - entity: sensor.internet_health_monitor_hop_1_latency_gateway
    name: Gateway
  - entity: sensor.internet_health_monitor_hop_2_latency_isp
    name: ISP
  - entity: sensor.internet_health_monitor_hop_3_latency_backbone
    name: Backbone
  - entity: sensor.internet_health_monitor_dns_latency
    name: DNS
```

### Status Card

```yaml
type: entities
title: Internet Health Monitor
entities:
  - entity: binary_sensor.internet_health_monitor_gateway_reachable
  - entity: binary_sensor.internet_health_monitor_internet_reachable
  - type: divider
  - entity: sensor.internet_health_monitor_hop_1_packet_loss_gateway
  - entity: sensor.internet_health_monitor_hop_2_packet_loss_isp
  - entity: sensor.internet_health_monitor_hop_2_jitter_isp
  - type: divider
  - entity: button.internet_health_monitor_refresh_diagnostics
```

## Requirements

- Home Assistant 2026.10.0 or newer, on a Linux host (HA OS, Container, Supervised or Core)
- `ip` and `ping` on the host (setup stops with an error naming any that are missing)
- `traceroute` for hops 2 and 3 (without it, those sensors stay unknown)

## Known Limitations

- **Three hops.** IHM watches hops 1 to 3: your gateway and the first routers
  past it. Problems further along the path show only in DNS latency.
- **It measures this host's own path.** One entry per Home Assistant; it
  cannot monitor another device's connection.
- **Containers on Docker Desktop see one hop.** Docker Desktop (Windows or
  macOS, including WSL2) hides the routers past its own bridge, so hops 2
  and 3 stay unknown. HA OS, a bridged VM, or Docker with host networking on
  Linux see the real path.
- **Some routers never answer.** A router that ignores traceroute or ping
  leaves its hop unknown or shows 100% loss, even when traffic passes through
  it normally.
- **Jitter needs history.** It is the spread of a hop's latency across polls,
  so it is unknown until the second poll and steadies over the first 30.
- **Fixed 60-second polling** (see [Polling](#polling)).
- **Hop ownership** finds no owner for private or shared ISP addresses
  (`10.x`, `100.64.x`), which many ISPs use on their first routers, and looks
  up IPv4 hops only.


### Setup fails: "Required system tools are missing"

The error names the missing tools. Install them on the Home Assistant host,
then reload the integration. HA OS and the official container include them.

### Hop 2 and 3 sensors show "Unknown"

- `traceroute` is not installed: `sudo apt install traceroute` (Debian/Ubuntu)
  or `apk add traceroute` (Alpine).
- Home Assistant runs in Docker Desktop (Windows or macOS): it hides the
  hops past its own bridge. Run HA on the real network (HA OS, a bridged VM,
  or Docker with host networking on Linux).
- Some routers do not answer traceroute. Press Reset network cache (enable it
  first) to detect the hops again.

### Gateway reachable is off, or no gateway is detected

IHM uses the host's default route. Check that the host has one
(`ip route show default`), then press Reset network cache.

## Quality Scale

Home Assistant grades only its built-in integrations against its [Integration Quality Scale](https://contributors.home-assistant.io/core/quality-scale/). This is a self-assessment against the same rules; each rule's status and evidence is in [quality_scale.yaml](custom_components/internet_health_monitor/quality_scale.yaml). A tier is reached when all of its rules and every rule below it are met.

<!-- BEGIN GENERATED: quality-scale (from custom_components/internet_health_monitor/quality_scale.yaml; run scripts/generate_quality_scale_table.py) -->
| Tier | Rules met | Open rules |
| ---- | --------- | ---------- |
| 🥉 Bronze | 19 / 20 | [`dependency-transparency`](https://contributors.home-assistant.io/core/quality-scale/dependency-transparency/) |
| 🥈 Silver | 10 / 10 | None |
| 🥇 Gold | 21 / 21 | None |
| 🏆 Platinum | 3 / 3 | None |
<!-- END GENERATED: quality-scale -->

## Command Line

The measurement engine is a separate package that runs without Home
Assistant (Linux): see
[packages/internet_health_monitor_core/README.md](packages/internet_health_monitor_core/README.md).

## Development

```bash
# Clone the repository
git clone https://github.com/solentlabs/internet-health-monitor.git
cd internet_health_monitor

# Set up development environments (needs uv: https://docs.astral.sh/uv/)
make setup           # .venv: oldest supported HA (2026.10.x), Python 3.14
make setup-current   # .venv-current: newest HA the test harness supports

# Run tests on both HA versions
make test-all

# Run linting
make check
```

## Solent Networks Suite

This integration is part of the **Solent Networks Suite** by Solent Labs:

- [Cable Modem Monitor](https://github.com/kwschulz/cable_modem_monitor) - Monitor your cable modem's signal quality
- [Internet Health Monitor](https://github.com/solentlabs/internet-health-monitor) - Track gateway latency, multi-hop visibility, and DNS health

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Solent Labs** - Network Monitoring Done Right
