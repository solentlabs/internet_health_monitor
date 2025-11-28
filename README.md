# HA Network Diagnostics

Home Assistant integration for network health monitoring.

## Features

- **Gateway Latency** - Ping your router/modem to measure local network latency
- **Gateway Jitter** - Track latency variance over time
- **Packet Loss** - Monitor dropped packets on your local network
- **ISP Latency** - Measure latency to your ISP's first hop (requires traceroute)
- **DNS Latency** - Monitor DNS resolution times

## Installation

### Manual Installation

1. Copy `custom_components/ha_network_diagnostics` to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration
4. Search for "Network Diagnostics"

### HACS (Coming Soon)

This integration will be available through HACS once publicly released.

## Configuration

During setup, you can configure:

| Option | Default | Description |
|--------|---------|-------------|
| Enable Gateway Monitoring | true | Monitor gateway latency, jitter, and packet loss |
| Enable DNS Monitoring | true | Monitor DNS resolution latency |
| Scan Interval | 60s | How often to run diagnostics |
| DNS Server | Auto | DNS server to test (auto-detects from system) |
| Ping Count | 3 | Number of pings per check |

## Sensors

| Sensor | Unit | Description |
|--------|------|-------------|
| Gateway Latency | ms | Round-trip time to your gateway |
| Gateway Jitter | ms | Standard deviation of recent latency measurements |
| Packet Loss | % | Percentage of dropped packets |
| ISP Latency | ms | Round-trip time to ISP's first router |
| DNS Latency | ms | Time to resolve a DNS query |

## Network Path Visualization

```
[HA Host] --Gateway Latency--> [Modem/Router] --ISP Latency--> [ISP Router] --DNS Latency--> [DNS Server]
          (local network)                      (your connection)            (internet)
```

## Requirements

- Home Assistant 2024.1.0 or newer
- Python 3.12+
- Linux host (for gateway detection via `ip route`)
- Optional: `traceroute` for ISP latency measurement
- Optional: `dig` for accurate DNS latency measurement

## Development

```bash
# Clone the repository
git clone https://github.com/kwschulz/ha_network_diagnostics.git
cd ha_network_diagnostics

# Set up development environment
make setup

# Run tests
make test

# Run linting
make check
```

## Related Projects

- [Cable Modem Monitor](https://github.com/kwschulz/cable_modem_monitor) - Monitor your cable modem's signal quality

## License

MIT License - see [LICENSE](LICENSE) for details.
