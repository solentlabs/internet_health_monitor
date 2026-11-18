# Dashboard Examples

Example Lovelace dashboard cards for Internet Health Monitor.

## Network Health Overview Card

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

## Multi-Hop Latency History Graph

Track latency through your entire network path over time:

```yaml
type: history-graph
title: Network Path Latency (24h)
hours_to_show: 24
entities:
  - entity: sensor.internet_health_monitor_hop_1_latency
    name: Hop 1 (Gateway)
  - entity: sensor.internet_health_monitor_hop_2_latency
    name: Hop 2 (ISP)
  - entity: sensor.internet_health_monitor_hop_3_latency
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
    entity: sensor.internet_health_monitor_gateway_latency
    name: Gateway Latency
    min: 0
    max: 100
    severity:
      green: 0
      yellow: 20
      red: 50
  - type: gauge
    entity: sensor.internet_health_monitor_hop_2_latency
    name: ISP Latency
    min: 0
    max: 100
    severity:
      green: 0
      yellow: 30
      red: 75
  - type: gauge
    entity: sensor.internet_health_monitor_packet_loss
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

## Conditional Card for Alerts

Show a card only when there are issues:

```yaml
type: conditional
conditions:
  - entity: sensor.internet_health_monitor_packet_loss
    state_not: "0.0"
card:
  type: markdown
  content: >
    ## Network Issues Detected

    Packet loss: {{ states('sensor.internet_health_monitor_packet_loss') }}%

    Gateway latency: {{ states('sensor.internet_health_monitor_gateway_latency') }}ms
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
  | 1 | Gateway | {{ states('sensor.internet_health_monitor_hop_1_latency') }} ms |
  | 2 | ISP | {{ states('sensor.internet_health_monitor_hop_2_latency') }} ms |
  | 3 | Backbone | {{ states('sensor.internet_health_monitor_hop_3_latency') }} ms |
  | - | DNS | {{ states('sensor.internet_health_monitor_dns_latency') }} ms |

  ---

  **Packet Loss:** {{ states('sensor.internet_health_monitor_packet_loss') }}%

  **Jitter:** {{ states('sensor.internet_health_monitor_gateway_jitter') }} ms

  **Gateway IP:** {{ state_attr('sensor.internet_health_monitor_gateway_latency', 'gateway_ip') }}

  **Hop 2 IP:** {{ state_attr('sensor.internet_health_monitor_hop_2_latency', 'hop_ip') }}
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
      - entity: sensor.internet_health_monitor_hop_1_latency
        name: Hop 1
      - entity: sensor.internet_health_monitor_hop_2_latency
        name: Hop 2
      - entity: sensor.internet_health_monitor_hop_3_latency
        name: Hop 3
      - entity: sensor.internet_health_monitor_dns_latency
        name: DNS

  # Health Metrics
  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.internet_health_monitor_packet_loss
        name: Loss %
        min: 0
        max: 5
        severity:
          green: 0
          yellow: 1
          red: 2
      - type: gauge
        entity: sensor.internet_health_monitor_gateway_jitter
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
      - entity: sensor.internet_health_monitor_hop_1_latency
      - entity: sensor.internet_health_monitor_hop_2_latency
      - entity: sensor.internet_health_monitor_hop_3_latency

  # Controls
  - type: horizontal-stack
    cards:
      - type: button
        entity: button.internet_health_monitor_refresh
        name: Refresh
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.internet_health_monitor_refresh
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
             and states('sensor.internet_health_monitor_hop_2_latency') | float(9999) < 50
             and states('sensor.internet_health_monitor_hop_1_packet_loss') | float(100) < 1 }}
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
    entity_id: sensor.internet_health_monitor_hop_2_latency
    above: 100
    for:
      minutes: 5
action:
  - service: notify.mobile_app
    data:
      message: "ISP latency is high: {{ states('sensor.internet_health_monitor_hop_2_latency') }}ms"
      title: "Network Alert"
```

### Alert on Packet Loss

```yaml
alias: "Network: Packet Loss Alert"
trigger:
  - platform: numeric_state
    entity_id: sensor.internet_health_monitor_packet_loss
    above: 1
    for:
      minutes: 2
action:
  - service: notify.mobile_app
    data:
      message: "Packet loss detected: {{ states('sensor.internet_health_monitor_packet_loss') }}%"
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
        Gateway: {{ states('sensor.internet_health_monitor_gateway_latency') }}ms
        ISP: {{ states('sensor.internet_health_monitor_hop_2_latency') }}ms
        DNS: {{ states('sensor.internet_health_monitor_dns_latency') }}ms
        Loss: {{ states('sensor.internet_health_monitor_packet_loss') }}%
```
