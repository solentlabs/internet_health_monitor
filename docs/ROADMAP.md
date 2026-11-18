# Internet Health Monitor - Roadmap

## Vision

The most comprehensive, easiest-to-configure network health monitoring integration for Home Assistant. Zero-config where possible, flexible where needed, rock-solid always.

**Part of the Solent Networks Suite** - designed for future correlation with Cable Modem Monitor and other network integrations.

---

## Why This Exists

| Existing Solution | Problem |
|-------------------|---------|
| HA Ping integration | Single IP, manual config, no jitter/loss sensors |
| HA Speedtest.net | No scheduling control, runs whenever, heavy |
| HANetProbe | Requires MQTT broker + external daemon |
| DIY template sensors | Fragile, no auto-detection, maintenance burden |

**Our answer:** One integration that does it all - auto-detects everything, schedules intelligently, surfaces clean sensors, and prepares data for correlation.

---

## Differentiators

1. **Zero-config auto-detection** - Gateway, DNS, ISP hops discovered automatically
2. **Multi-hop network path visibility** - Latency at each hop (1, 2, 3+) - unique in HA ecosystem
3. **Scheduled bandwidth testing** - User controls when heavy tests run (not random)
4. **Pluggable backends** - User picks the speed test service; each is a drop-in module (docs/SPEED_TEST_BACKENDS.md)
5. **Unified configuration** - One integration, one options flow, done
6. **Correlation-ready** - Clean data model designed for Solent Aggregator

---

## Architecture

```
Internet Health Monitor
├── Lightweight Monitors (always running, minimal impact)
│   ├── Gateway latency/jitter/packet loss
│   ├── Multi-hop latency (hop 1, 2, 3, ...)
│   └── DNS latency
│
├── Scheduled Heavy Tests (user-controlled)
│   ├── Bandwidth (download/upload)
│   └── Full traceroute
│
└── Pluggable Backends (one module each, docs/SPEED_TEST_BACKENDS.md)
    └── Cloudflare, M-Lab NDT7, Fast.com, LibreSpeed
```

### File Structure

```
custom_components/internet_health_monitor/
├── __init__.py              # Integration setup, coordinators
├── config_flow.py           # Config + options flow
├── const.py                 # Constants, defaults
├── sensor.py                # All sensor entities
├── button.py                # Refresh/reset/run-speedtest buttons
├── binary_sensor.py         # Connection health, reachability
├── diagnostics.py           # HA diagnostics download
├── strings.json             # English strings
├── translations/            # Multi-language support
│   ├── en.json
│   ├── de.json
│   ├── es.json
│   ├── fr.json
│   └── pt-BR.json
└── core/
    ├── network_diagnostics.py   # Lightweight monitoring
    ├── multi_hop.py             # Traceroute-based hop analysis
    ├── bandwidth.py             # Bandwidth testing
    └── backends/                # Pluggable bandwidth backends
        ├── base.py              # Abstract backend
        ├── cloudflare.py
        ├── ndt7.py              # M-Lab
        ├── fastcom.py
        └── librespeed.py
```

---

## Path to Release

Set 2026-11-18. Each stage finishes before the next starts. Cable Modem
Monitor is the reference for how each is done.

1. **Local.** Everything that can be built and tested locally is: core as
   a portable package (ADR-005), modular backends (ADR-003), tests and
   coverage gates, icon, configuration UX, a customizable entity name
   prefix, sensor history (long-term statistics), metrics.
2. **GitHub.** Push to `solentlabs/internet-health-monitor` with CI.
3. **Live HA.** Install on the developer's deployed HA from GitHub and
   verify on a real network path (hops 2 and 3 cannot be seen from
   Docker Desktop: ARCHITECTURE.md).
4. **Publish.** Release zip installs, then HACS submission.

---

## Feature Specification

### Tier 1: Lightweight Monitoring (Continuous)

Runs every N seconds (default 60), minimal network impact.

| Sensor | Unit | Description | Auto-Detect |
|--------|------|-------------|-------------|
| `gateway_latency` | ms | RTT to gateway (router/modem) | ✓ via `ip route` |
| `gateway_jitter` | ms | Latency variance (stddev) | - |
| `packet_loss` | % | Lost packets over interval | - |
| `hop_1_latency` | ms | First hop (usually gateway) | ✓ via traceroute |
| `hop_2_latency` | ms | Second hop (usually ISP) | ✓ |
| `hop_3_latency` | ms | Third hop (ISP backbone) | ✓ |
| `dns_latency` | ms | DNS resolution time | ✓ system DNS |

**Attributes on hop sensors:**
- `hop_ip`: IP address of this hop
- `hop_hostname`: Reverse DNS (if available)
- `reachable`: Boolean

### Tier 2: Environment Detection

| Sensor | Values | Description |
|--------|--------|-------------|
| `connection_type` | `ethernet`, `wifi`, `unknown` | How HA host connects |
| `environment` | `native`, `container`, `vm`, `unknown` | HA deployment type |

### Tier 3: Scheduled Bandwidth Testing

User-controlled schedule. Never runs without explicit configuration.

| Sensor | Unit | Description |
|--------|------|-------------|
| `download_speed` | Mbit/s | Last measured download |
| `upload_speed` | Mbit/s | Last measured upload |
| `bandwidth_ping` | ms | Latency during speed test |
| `last_bandwidth_test` | timestamp | When last test ran |

**Schedule Options:**
```yaml
bandwidth_schedule:
  - "02:00"      # Daily at 2 AM
  - "14:00"      # And 2 PM
  # Or: "manual" - only via button/service call
```

**Backend Options:**
```yaml
bandwidth_backend:
  - none                 # Disabled (default)
  - cloudflare
  - mlab_ndt7
  - fastcom
  - librespeed
```

### Buttons

| Button | Action |
|--------|--------|
| Refresh Diagnostics | Force immediate lightweight check |
| Reset Network Cache | Clear cached gateway/hop IPs, re-detect |
| Run Bandwidth Test | Trigger on-demand speed test |

### Binary Sensors

| Sensor | Description |
|--------|-------------|
| `gateway_reachable` | Is gateway responding? |
| `internet_reachable` | Is DNS/external hop responding? |

---

## Config Flow

### Initial Setup (Zero-Config Default)

```
┌─────────────────────────────────────────────┐
│  Internet Health Monitor                     │
├─────────────────────────────────────────────┤
│                                              │
│  ✓ Auto-detect gateway                       │
│  ✓ Auto-detect DNS server                    │
│  ✓ Enable network path monitoring            │
│                                              │
│  Scan interval: [60] seconds                 │
│                                              │
│  [ ] Enable bandwidth testing                │
│      └─ Schedule: [Manual only ▼]            │
│      └─ Backend: [Built-in ▼]                │
│                                              │
│              [Submit]                        │
└─────────────────────────────────────────────┘
```

### Options Flow (Advanced)

```
┌─────────────────────────────────────────────┐
│  Internet Health Monitor Options             │
├─────────────────────────────────────────────┤
│                                              │
│  Lightweight Monitoring                      │
│  ───────────────────                         │
│  [x] Gateway monitoring                      │
│  [x] Multi-hop monitoring (hops 1-3)         │
│  [x] DNS monitoring                          │
│  Scan interval: [60] seconds                 │
│  Ping count: [3]                             │
│  Max hops to trace: [3]                      │
│                                              │
│  DNS Server                                  │
│  ──────────                                  │
│  [Auto-detect ▼]                             │
│    • Auto-detect (system)                    │
│    • 1.1.1.1 (Cloudflare)                   │
│    • 8.8.8.8 (Google)                       │
│    • 9.9.9.9 (Quad9)                        │
│    • Custom...                               │
│                                              │
│  Bandwidth Testing                           │
│  ─────────────────                           │
│  [x] Enable bandwidth testing                │
│  Backend: [M-Lab NDT7 ▼]                     │
│    • Cloudflare                              │
│    • M-Lab NDT7                              │
│    • Fast.com                                │
│    • LibreSpeed                              │
│                                              │
│  Schedule: [Custom ▼]                        │
│    • Manual only                             │
│    • Every 6 hours                           │
│    • Every 12 hours                          │
│    • Daily at 2 AM                           │
│    • Custom...                               │
│                                              │
│  Custom schedule: [02:00, 14:00]             │
│                                              │
│              [Submit]                        │
└─────────────────────────────────────────────┘
```

---

## Sensor Examples

```yaml
sensor.internet_health_gateway_latency:
  state: 2.4
  unit_of_measurement: ms
  attributes:
    gateway_ip: 192.168.1.1
    reachable: true

sensor.internet_health_hop_2_latency:
  state: 15.3
  unit_of_measurement: ms
  attributes:
    hop_ip: 10.0.0.1
    hop_hostname: ae-5.r01.atlnga05.us.bb.gin.ntt.net
    reachable: true
    hop_number: 2

sensor.internet_health_download_speed:
  state: 245.6
  unit_of_measurement: Mbit/s
  attributes:
    backend: cloudflare
    server: Cloudflare (ATL)
    last_test: "2025-12-03T02:00:00Z"

```

---

## Error Handling

| Component | Failure Mode | Behavior |
|-----------|--------------|----------|
| Gateway detect | `ip route` fails | `gateway_ip: null`, sensor unavailable |
| Gateway ping | Timeout | `gateway_latency: null`, `reachable: false` |
| Multi-hop trace | `traceroute` unavailable | Graceful disable, log warning |
| DNS check | Timeout/failure | `dns_latency: null`, `success: false` |
| Bandwidth test | Tool unavailable | Graceful disable, suggest alternatives |

**Principle:** Each check is isolated. One failure never cascades.

---

## Implementation Checklist

### Phase 1: Core Foundation ✓ (Existing)
- [x] Gateway latency/jitter/packet loss
- [x] ISP hop detection (single hop)
- [x] DNS latency
- [x] Config flow + options flow
- [x] Refresh/reset buttons
- [x] DataUpdateCoordinator pattern
- [x] Basic tests

### Phase 2: Multi-Hop & Polish
- [ ] Multi-hop implementation (hops 1, 2, 3+)
  - [ ] Extend traceroute parsing for multiple hops
  - [ ] Create HopLatencySensor for each hop
  - [ ] Add hop count to config options
  - [ ] Cache hop IPs, refresh on reset
- [ ] Wire up config toggles (gateway/DNS/ISP enable flags)
- [ ] Binary sensors (reachable)
- [ ] Solent Labs branding in device info
- [ ] Bundled dashboard card, following CMM's pattern (pattern reuse, no
      code dependency: ARCHITECTURE_DECISIONS.md ADR-002). Reference:
      CMM `custom_components/cable_modem_monitor/docs/DASHBOARD_CARD_SPEC.md`
      and `card/`.
  - [ ] Card in the dashboard's Add card list, configured by form, no YAML
  - [ ] `generate_dashboard_card` action returning the card's YAML
  - [ ] Card failing to load never stops monitoring
  - [ ] Shows each measurement separately (no composite, ADR-004)

### Phase 3: Bandwidth Testing
- [ ] Core bandwidth module (`core/bandwidth.py`)
- [ ] Backend interface (ADR-003): download, upload, idle and loaded latency per direction
- [ ] Backends, one module each (docs/SPEED_TEST_BACKENDS.md)
  - [ ] Cloudflare
  - [ ] M-Lab NDT7
  - [ ] Fast.com
  - [ ] LibreSpeed
- [ ] Scheduling system
  - [ ] Cron-like schedule parsing
  - [ ] Manual-only mode
  - [ ] "Run Bandwidth Test" button
- [ ] Bandwidth sensors (download, upload, ping)

### Phase 4: Environment Detection
- [ ] Connection type detection (wifi/ethernet)
- [ ] Environment detection (native/container/VM)
- [ ] Sensors for each

### Phase 5: Quality & Release
- [ ] Multi-language support
  - [ ] German (de)
  - [ ] Spanish (es)
  - [ ] French (fr)
  - [ ] Brazilian Portuguese (pt-BR)
- [ ] Comprehensive test coverage
  - [ ] Unit tests for all core modules
  - [ ] Integration tests with HA
  - [ ] Mock external tools (ping, traceroute, speedtest)
  - [ ] Security review (no command injection, etc.)
- [ ] Documentation
  - [ ] README with examples
  - [ ] Dashboard examples
  - [ ] Troubleshooting guide
- [ ] Local testing
  - [ ] Run on dev laptop
  - [ ] Deploy to real HA instance
- [ ] DevOps
  - [ ] GitHub repo under solentlabs org
  - [ ] CI/CD pipeline (tests, linting, release)
  - [ ] Branch protection
  - [ ] Release automation
- [ ] HACS submission

---

## Non-Goals (Out of Scope)

- **Reading other HA speed test integrations** - IHM runs its own tests (ADR-003)
- **Composite health scores** - Each entity reports one measurement; build composites in HA (ARCHITECTURE_DECISIONS.md ADR-004)
- **Correlation/diagnosis** - That's the Aggregator's job
- **Historical storage** - HA recorder handles this
- **Alerting/notifications** - Use HA automations
- **Cloud telemetry** - All data stays local
- **Router/modem configuration** - Read-only monitoring

---

## Future Considerations (Post-v1.0)

- IPv6 support for all detection
- Custom hop targets (user-specified IPs to trace)
- Per-hop jitter tracking
- Network interface selection (for multi-NIC hosts)
- SNMP polling for router stats
- Integration with Solent Aggregator for correlation

---

## Success Criteria

**v1.0.0 is ready when:**

1. Zero-config setup works on fresh HA install
2. All Tier 1-3 sensors functional
3. Multi-hop latency is unique differentiator
4. Bandwidth testing is scheduled and pluggable
5. 90%+ test coverage
6. Multi-language support (5 languages)
7. Tested on real HA instance (not just dev)
8. Documentation complete
9. HACS-ready

---

*Created: 2025-11-28*
*Updated: 2025-12-03*
*Status: Planning complete, Phase 2 starting*

---

**Solent Labs™** - Network Monitoring Done Right
