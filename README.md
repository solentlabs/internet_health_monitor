# Internet Health Monitor

[![Solent Networks Suite](https://img.shields.io/badge/Solent%20Networks-Suite-blue)](https://github.com/solentlabs)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A **Solent Labs** Home Assistant integration for comprehensive internet health monitoring with multi-hop network path visibility.

Part of the **Solent Networks Suite** - tools for comprehensive home network visibility.

## Features

- **Multi-Hop Latency** - Trace latency through your entire network path (gateway, ISP, backbone)
- **Gateway Monitoring** - Ping your router/modem to measure local network latency and jitter
- **Packet Loss Tracking** - Monitor dropped packets on your local network
- **DNS Latency** - Monitor DNS resolution times with accurate RTT measurement
- **Binary Sensors** - Gateway reachable and internet reachable status

### What Makes This Different

| Feature | Other Solutions | Internet Health Monitor |
|---------|-----------------|------------------------|
| Gateway Detection | Manual config | Auto-detected via `ip route` |
| Multi-hop Visibility | Single target only | Trace hops 1-10 (unique in HA) |
| DNS Latency | Cache-affected | Accurate RTT via `dig` |
| Configuration | YAML editing | Zero-config UI setup |

## Installation

### Manual Installation

1. Copy `custom_components/internet_health_monitor` to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration
4. Search for "Internet Health Monitor"

### HACS (Coming Soon)

This integration will be available through HACS once publicly released.

## Configuration

During setup, you can configure:

| Option | Default | Description |
|--------|---------|-------------|
| Enable Gateway Monitoring | true | Monitor gateway latency, jitter, and packet loss |
| Enable Multi-Hop Latency | true | Trace latency through network path |
| Maximum Hops | 3 | Number of hops to trace (1-10) |
| Enable DNS Monitoring | true | Monitor DNS resolution latency |
| Scan Interval | 60s | How often to run diagnostics |
| DNS Server | Auto | DNS server to test (auto-detects from system) |
| Ping Count | 3 | Number of pings per check |

## Sensors

### Latency Sensors

| Sensor | Unit | Description |
|--------|------|-------------|
| Gateway Latency | ms | Round-trip time to your gateway |
| Gateway Jitter | ms | Standard deviation of recent latency measurements |
| Hop 1 Latency | ms | First network hop (usually your gateway) |
| Hop 2 Latency | ms | Second hop (usually ISP first router) |
| Hop 3 Latency | ms | Third hop (ISP backbone) |
| DNS Latency | ms | Time to resolve a DNS query |
| Packet Loss | % | Percentage of dropped packets |

### Binary Sensors

| Sensor | Description |
|--------|-------------|
| Gateway Reachable | Whether the gateway is responding to pings |
| Internet Reachable | Whether DNS resolution is successful |

### Buttons

| Button | Description |
|--------|-------------|
| Refresh | Force immediate diagnostic check |
| Reset Network Cache | Clear cached IPs and re-detect |

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

### Network Health Overview

A glance card showing all network metrics at once:

```yaml
type: glance
title: Network Health
entities:
  - entity: sensor.internet_health_monitor_gateway_latency
    name: Gateway
  - entity: sensor.internet_health_monitor_hop_1_latency
    name: Hop 1
  - entity: sensor.internet_health_monitor_hop_2_latency
    name: Hop 2
  - entity: sensor.internet_health_monitor_hop_3_latency
    name: Hop 3
  - entity: sensor.internet_health_monitor_dns_latency
    name: DNS
```

### Multi-Hop Latency Graph

Track latency through your entire network path:

```yaml
type: history-graph
title: Network Path Latency (24h)
hours_to_show: 24
entities:
  - entity: sensor.internet_health_monitor_gateway_latency
    name: Gateway
  - entity: sensor.internet_health_monitor_hop_1_latency
    name: Hop 1
  - entity: sensor.internet_health_monitor_hop_2_latency
    name: Hop 2 (ISP)
  - entity: sensor.internet_health_monitor_hop_3_latency
    name: Hop 3
  - entity: sensor.internet_health_monitor_dns_latency
    name: DNS
```

### Network Status Entities Card

```yaml
type: entities
title: Internet Health Monitor
entities:
  - entity: binary_sensor.internet_health_monitor_gateway_reachable
    name: Gateway Status
  - entity: binary_sensor.internet_health_monitor_internet_reachable
    name: Internet Status
  - type: divider
  - entity: sensor.internet_health_monitor_gateway_latency
    secondary_info: last-updated
  - entity: sensor.internet_health_monitor_gateway_jitter
  - entity: sensor.internet_health_monitor_packet_loss
  - type: divider
  - entity: sensor.internet_health_monitor_hop_1_latency
    name: Hop 1 (Gateway)
  - entity: sensor.internet_health_monitor_hop_2_latency
    name: Hop 2 (ISP)
  - entity: sensor.internet_health_monitor_hop_3_latency
    name: Hop 3 (Backbone)
  - type: divider
  - entity: sensor.internet_health_monitor_dns_latency
  - type: divider
  - entity: button.internet_health_monitor_refresh
    name: Refresh Now
  - entity: button.internet_health_monitor_reset_network_cache
    name: Reset Cache
```

### Network Path Markdown Card

```yaml
type: markdown
title: Network Path
content: >
  ## Current Latency

  | Hop | Latency |
  |-----|---------|
  | Gateway | {{ states('sensor.internet_health_monitor_gateway_latency') }} ms |
  | Hop 1 | {{ states('sensor.internet_health_monitor_hop_1_latency') }} ms |
  | Hop 2 (ISP) | {{ states('sensor.internet_health_monitor_hop_2_latency') }} ms |
  | Hop 3 | {{ states('sensor.internet_health_monitor_hop_3_latency') }} ms |
  | DNS | {{ states('sensor.internet_health_monitor_dns_latency') }} ms |

  **Packet Loss:** {{ states('sensor.internet_health_monitor_packet_loss') }}%
  **Jitter:** {{ states('sensor.internet_health_monitor_gateway_jitter') }} ms
```

### Mini Graph Card (HACS)

If you have the mini-graph-card installed via HACS:

```yaml
type: custom:mini-graph-card
name: Network Path Latency
entities:
  - entity: sensor.internet_health_monitor_hop_1_latency
    name: Hop 1
    color: "#4CAF50"
  - entity: sensor.internet_health_monitor_hop_2_latency
    name: Hop 2
    color: "#2196F3"
  - entity: sensor.internet_health_monitor_hop_3_latency
    name: Hop 3
    color: "#FF9800"
  - entity: sensor.internet_health_monitor_dns_latency
    name: DNS
    color: "#9C27B0"
hours_to_show: 6
points_per_hour: 12
line_width: 2
show:
  labels: true
  points: false
```

## Requirements

- Home Assistant 2025.1.0 or newer
- Python 3.12+
- Linux host (for gateway detection via `ip route`)
- `traceroute` command (for multi-hop latency)
- Optional: `dig` for accurate DNS latency measurement

## Troubleshooting

### Hop sensors show "Unknown"

Make sure `traceroute` is installed on your Home Assistant host:

```bash
# Debian/Ubuntu
sudo apt install traceroute

# Alpine (HA OS container)
apk add traceroute
```

### Gateway not detected

The integration uses `ip route show default` to detect your gateway. If this fails:
1. Check that your HA host has a default route
2. Manually configure your gateway IP in Home Assistant

### DNS latency is very low (0-1ms)

This usually means the `dig` command is not available and the integration is falling back to cached DNS resolution. Install bind-tools for accurate measurement:

```bash
# Debian/Ubuntu
sudo apt install dnsutils

# Alpine
apk add bind-tools
```

## Development

```bash
# Clone the repository
git clone https://github.com/solentlabs/internet-health-monitor.git
cd internet_health_monitor

# Set up development environments (needs uv: https://docs.astral.sh/uv/)
make setup           # Python 3.12, oldest supported HA (2025.1.x)
make setup-current   # Python 3.14, newest HA

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
