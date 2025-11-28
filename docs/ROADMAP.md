# HA Network Diagnostics Roadmap

## Vision

Provide holistic network health monitoring for Home Assistant, enabling users to diagnose connectivity issues and correlate network performance with other integrations.

## Tiers

### Tier 1: Lightweight Network Diagnostics (v0.1.0) - CURRENT

Independent polling, minimal network impact.

| Metric | Implementation | Sensor |
|--------|---------------|--------|
| Gateway latency | ICMP ping to default gateway | `sensor.network_diagnostics_gateway_latency` |
| Gateway jitter | Stddev of last N pings | `sensor.network_diagnostics_gateway_jitter` |
| Packet loss | % failed over last N pings | `sensor.network_diagnostics_packet_loss` |
| ISP latency | Ping to first ISP hop | `sensor.network_diagnostics_isp_latency` |
| DNS resolution time | Timed lookup to configured server | `sensor.network_diagnostics_dns_latency` |

### Tier 2: Environment Detection (v0.2.0)

Detect HA host environment for context.

| Metric | Implementation | Sensor |
|--------|---------------|--------|
| Connection type | Detect wifi/ethernet | `sensor.network_diagnostics_connection_type` |
| Environment | Detect native/container/VM | `sensor.network_diagnostics_environment` |

### Tier 3: Heavy Diagnostics (v1.0.0+)

User-scheduled, bandwidth-intensive tests.

| Metric | Implementation | Frequency |
|--------|---------------|-----------|
| Download speed | speedtest-cli / iperf | 1-4x daily |
| Upload speed | speedtest-cli / iperf | 1-4x daily |
| Traceroute | Full path analysis | On-demand |

### Tier 4: Correlation & Analytics (Future)

Integration with other network integrations.

- Anomaly detection with configurable thresholds
- Correlation with modem integrations (cable_modem_monitor, etc.)
- Historical trend analysis
- Opt-in telemetry for aggregate insights

---

## Architecture

```
ha_network_diagnostics/
├── __init__.py              # Integration setup, coordinator
├── config_flow.py           # Config + options flow
├── const.py                 # Constants
├── sensor.py                # Sensor entities
├── button.py                # Refresh/reset buttons
└── core/
    └── network_diagnostics.py  # Core diagnostics logic
```

### Coordinator Pattern

```
__init__.py
  └── network_coordinator
        update_interval: 60s (user configurable)
        └── NetworkDiagnostics
              └── Sensors: gateway_latency, jitter, packet_loss, isp_latency, dns_latency
```

---

## Sensors

```python
sensor.network_diagnostics_gateway_latency
  state: 2.4
  unit: ms
  attributes:
    gateway_ip: 192.168.1.1
    reachable: true

sensor.network_diagnostics_gateway_jitter
  state: 1.2
  unit: ms

sensor.network_diagnostics_packet_loss
  state: 0.0
  unit: "%"
  attributes:
    packets_sent: 3
    packets_received: 3

sensor.network_diagnostics_isp_latency
  state: 15.3
  unit: ms
  attributes:
    isp_hop_ip: 10.0.0.1
    reachable: true

sensor.network_diagnostics_dns_latency
  state: 12.5
  unit: ms
  attributes:
    dns_server: 1.1.1.1
    success: true
```

---

## Config Flow

```
# Initial setup
[x] Enable gateway monitoring
[x] Enable DNS monitoring
Scan interval: [60] seconds
DNS Server: [Auto-detect ▼]
  - Auto-detect (system)
  - 1.1.1.1 (Cloudflare)
  - 8.8.8.8 (Google)
  - 9.9.9.9 (Quad9)
  - Custom...
Ping count: [3]
```

---

## Error Handling

| Component | Failure Mode | Result |
|-----------|--------------|--------|
| Gateway detect | `ip route` fails | `gateway_ip: null, reachable: false` |
| Gateway ping | No response / timeout | `gateway_latency: null, reachable: false` |
| ISP hop detect | `traceroute` unavailable | `isp_hop_ip: null` (feature disabled) |
| DNS check | Timeout / NXDOMAIN | `dns_latency: null, success: false` |

**Principle:** Each check is isolated. One failure doesn't affect others.

---

## Dependencies

**Tier 1 (current):**
- `asyncio` subprocess for ping
- `socket` for DNS timing (stdlib)
- Optional: `dig` for accurate DNS latency
- Optional: `traceroute` for ISP hop detection

**Tier 3 (future):**
- `speedtest-cli` or `iperf3` for bandwidth tests
- Consider `icmplib` for pure-Python ICMP

---

## Privacy Considerations

All data is local by default. Future opt-in telemetry would only collect:
- Aggregate latency ranges (not raw values)
- Packet loss percentages
- No IP addresses, no gateway IPs, no DNS servers

---

## Correlation Value

The unique value proposition when combined with modem integrations:

| Scenario | Modem Data | Network Data | Diagnosis |
|----------|-----------|--------------|-----------|
| Line issue | SNR drops | Latency spikes, packet loss | Physical/ISP problem |
| Modem overload | Stats normal | Latency high | Modem CPU/memory issue |
| DNS issue | Stats normal | DNS slow, ping fine | DNS server problem |
| ISP routing | Stats normal | High latency, no loss | Upstream congestion |

---

## Implementation Status

### Tier 1 Checklist

- [x] Create `core/network_diagnostics.py`
  - [x] `NetworkDiagnostics` class
  - [x] Auto-detect gateway (`ip route`)
  - [x] Gateway ping with jitter calculation
  - [x] Packet loss tracking
  - [x] DNS resolution timing
  - [x] ISP hop detection (traceroute)

- [x] Create `__init__.py`
  - [x] DataUpdateCoordinator setup
  - [x] Options update listener

- [x] Create `sensor.py`
  - [x] GatewayLatencySensor
  - [x] GatewayJitterSensor
  - [x] PacketLossSensor
  - [x] ISPLatencySensor
  - [x] DNSLatencySensor

- [x] Create `config_flow.py`
  - [x] Initial config flow
  - [x] Options flow

- [x] Create `button.py`
  - [x] Refresh Diagnostics button
  - [x] Reset Cache button

- [x] Tests
  - [x] `tests/core/test_network_diagnostics.py`

- [ ] Environment detection (Tier 2)
- [ ] Speed tests (Tier 3)

---

*Created: 2025-11-28*
*Status: Tier 1 complete*
