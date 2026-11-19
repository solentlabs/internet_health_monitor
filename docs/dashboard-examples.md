# Dashboard Examples

Example Lovelace dashboard cards for Internet Health Monitor.

## Network Health Overview Card

A glance card showing all network metrics at once:

```yaml
type: glance
title: Network Health
entities:
  - entity: sensor.internet_health_monitor_hop_1_latency_gateway
    name: Gateway
  - entity: sensor.internet_health_monitor_hop_1_latency_gateway
    name: Hop 1
  - entity: sensor.internet_health_monitor_hop_2_latency_isp
    name: Hop 2
  - entity: sensor.internet_health_monitor_hop_3_latency_backbone
    name: Hop 3
  - entity: sensor.internet_health_monitor_dns_latency
    name: DNS
```

## Multi-Hop Latency History Graph

Track latency through your entire network path over time:

```yaml
type: history-graph
title: Network Path Latency (24h)
hours_to_show: 24
entities:
  - entity: sensor.internet_health_monitor_hop_1_latency_gateway
    name: Hop 1 (Gateway)
  - entity: sensor.internet_health_monitor_hop_2_latency_isp
    name: Hop 2 (ISP)
  - entity: sensor.internet_health_monitor_hop_3_latency_backbone
    name: Hop 3 (Backbone)
  - entity: sensor.internet_health_monitor_dns_latency
    name: DNS
```

## Network Status with Gauges

Visual gauges for key metrics:

```yaml
type: vertical-stack
cards:
  - type: gauge
    entity: sensor.internet_health_monitor_hop_1_latency_gateway
    name: Gateway Latency
    min: 0
    max: 100
    severity:
      green: 0
      yellow: 20
      red: 50
  - type: gauge
    entity: sensor.internet_health_monitor_hop_2_latency_isp
    name: ISP Latency
    min: 0
    max: 100
    severity:
      green: 0
      yellow: 30
      red: 75
  - type: gauge
    entity: sensor.internet_health_monitor_hop_1_packet_loss_gateway
    name: Packet Loss
    min: 0
    max: 10
    severity:
      green: 0
      yellow: 1
      red: 5
```

## Mini Graph Card (HACS)

If you have the mini-graph-card installed via HACS:

```yaml
type: custom:mini-graph-card
name: Network Path Latency
entities:
  - entity: sensor.internet_health_monitor_hop_1_latency_gateway
    name: Hop 1
    color: "#4CAF50"
  - entity: sensor.internet_health_monitor_hop_2_latency_isp
    name: Hop 2
    color: "#2196F3"
  - entity: sensor.internet_health_monitor_hop_3_latency_backbone
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

## Entities Card with Controls

Show status with buttons for manual control:

```yaml
type: entities
title: Internet Health Monitor
entities:
  - entity: binary_sensor.internet_health_monitor_gateway_reachable
    name: Gateway Status
  - entity: binary_sensor.internet_health_monitor_internet_reachable
    name: Internet Status
  - type: divider
  - entity: sensor.internet_health_monitor_hop_1_latency_gateway
    secondary_info: last-updated
  - entity: sensor.internet_health_monitor_hop_1_jitter_gateway
  - entity: sensor.internet_health_monitor_hop_1_packet_loss_gateway
  - type: divider
  - entity: sensor.internet_health_monitor_hop_1_latency_gateway
    name: Hop 1 (Gateway)
  - entity: sensor.internet_health_monitor_hop_2_latency_isp
    name: Hop 2 (ISP)
  - entity: sensor.internet_health_monitor_hop_3_latency_backbone
    name: Hop 3 (Backbone)
  - type: divider
  - entity: sensor.internet_health_monitor_dns_latency
  - type: divider
  - entity: button.internet_health_monitor_refresh_diagnostics
    name: Refresh Now
  - entity: button.internet_health_monitor_reset_network_cache
    name: Reset Cache
```

## Conditional Card for Alerts

Show a card only when there are issues:

```yaml
type: conditional
conditions:
  - entity: sensor.internet_health_monitor_hop_1_packet_loss_gateway
    state_not: "0.0"
card:
  type: markdown
  content: >
    ## Network Issues Detected

    Packet loss: {{ states('sensor.internet_health_monitor_hop_1_packet_loss_gateway') }}%

    Gateway latency: {{ states('sensor.internet_health_monitor_hop_1_latency_gateway') }}ms
```

## Network Path Visualization

A markdown card showing the network path with latencies:

```yaml
type: markdown
title: Network Path
content: >
  ## Current Latency Through Network Path

  | Hop | Target | Latency |
  |-----|--------|---------|
  | 1 | Gateway | {{ states('sensor.internet_health_monitor_hop_1_latency_gateway') }} ms |
  | 2 | ISP | {{ states('sensor.internet_health_monitor_hop_2_latency_isp') }} ms |
  | 3 | Backbone | {{ states('sensor.internet_health_monitor_hop_3_latency_backbone') }} ms |
  | - | DNS | {{ states('sensor.internet_health_monitor_dns_latency') }} ms |

  ---

  **Packet Loss:** {{ states('sensor.internet_health_monitor_hop_1_packet_loss_gateway') }}%

  **Jitter:** {{ states('sensor.internet_health_monitor_hop_1_jitter_gateway') }} ms

  **Gateway IP:** {{ state_attr('sensor.internet_health_monitor_hop_1_latency_gateway', 'hop_ip') }}

  **Hop 2 IP:** {{ state_attr('sensor.internet_health_monitor_hop_2_latency_isp', 'hop_ip') }}
```

## Complete Dashboard Example

A full dashboard layout combining multiple cards:

```yaml
type: vertical-stack
cards:
  # Status Row
  - type: horizontal-stack
    cards:
      - type: entity
        entity: binary_sensor.internet_health_monitor_gateway_reachable
        name: Gateway
      - type: entity
        entity: binary_sensor.internet_health_monitor_internet_reachable
        name: Internet

  # Latency Overview
  - type: glance
    title: Network Latency
    entities:
      - entity: sensor.internet_health_monitor_hop_1_latency_gateway
        name: Hop 1
      - entity: sensor.internet_health_monitor_hop_2_latency_isp
        name: Hop 2
      - entity: sensor.internet_health_monitor_hop_3_latency_backbone
        name: Hop 3
      - entity: sensor.internet_health_monitor_dns_latency
        name: DNS

  # Health Metrics
  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.internet_health_monitor_hop_1_packet_loss_gateway
        name: Loss %
        min: 0
        max: 5
        severity:
          green: 0
          yellow: 1
          red: 2
      - type: gauge
        entity: sensor.internet_health_monitor_hop_1_jitter_gateway
        name: Jitter
        min: 0
        max: 20
        severity:
          green: 0
          yellow: 5
          red: 10

  # History Graph
  - type: history-graph
    title: Latency History (6h)
    hours_to_show: 6
    entities:
      - entity: sensor.internet_health_monitor_hop_1_latency_gateway
      - entity: sensor.internet_health_monitor_hop_2_latency_isp
      - entity: sensor.internet_health_monitor_hop_3_latency_backbone

  # Controls
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.internet_health_monitor_refresh_diagnostics
        name: Refresh
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.internet_health_monitor_refresh_diagnostics
      - type: button
        entity: button.internet_health_monitor_reset_network_cache
        name: Reset Cache
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.internet_health_monitor_reset_network_cache
```

---

## Build Your Own Health Check

IHM reports each measurement separately and does not combine them into
a score
([ARCHITECTURE_DECISIONS.md § ADR-004](ARCHITECTURE_DECISIONS.md#adr-004-no-composite-health-sensors)).
If you want one on/off "healthy" signal, define it with your own
thresholds as a template binary sensor in `configuration.yaml`. The
numbers below are placeholders; pick values that suit your connection.

```yaml
template:
  - binary_sensor:
      - name: "Connection healthy"
        state: >
          {{ is_state('binary_sensor.internet_health_monitor_gateway_reachable', 'on')
             and is_state('binary_sensor.internet_health_monitor_internet_reachable', 'on')
             and states('sensor.internet_health_monitor_hop_2_latency_isp') | float(9999) < 50
             and states('sensor.internet_health_monitor_hop_1_packet_loss_gateway') | float(100) < 1 }}
```

Because each input stays its own entity, a history graph still shows
which one went wrong.

---

## Automation Examples

### Alert on High Latency

```yaml
alias: "Network: High Latency Alert"
trigger:
  - platform: numeric_state
    entity_id: sensor.internet_health_monitor_hop_2_latency_isp
    above: 100
    for:
      minutes: 5
action:
  - service: notify.mobile_app
    data:
      message: "ISP latency is high: {{ states('sensor.internet_health_monitor_hop_2_latency_isp') }}ms"
      title: "Network Alert"
```

### Alert on Packet Loss

```yaml
alias: "Network: Packet Loss Alert"
trigger:
  - platform: numeric_state
    entity_id: sensor.internet_health_monitor_hop_1_packet_loss_gateway
    above: 1
    for:
      minutes: 2
action:
  - service: notify.mobile_app
    data:
      message: "Packet loss detected: {{ states('sensor.internet_health_monitor_hop_1_packet_loss_gateway') }}%"
      title: "Network Issue"
```

### Daily Network Health Report

```yaml
alias: "Network: Daily Health Report"
trigger:
  - platform: time
    at: "08:00:00"
action:
  - service: notify.mobile_app
    data:
      title: "Daily Network Report"
      message: >
        Gateway: {{ states('sensor.internet_health_monitor_hop_1_latency_gateway') }}ms
        ISP: {{ states('sensor.internet_health_monitor_hop_2_latency_isp') }}ms
        DNS: {{ states('sensor.internet_health_monitor_dns_latency') }}ms
        Loss: {{ states('sensor.internet_health_monitor_hop_1_packet_loss_gateway') }}%
```
