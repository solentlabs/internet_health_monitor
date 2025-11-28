# Dashboard Examples

Example Lovelace dashboard cards for HA Network Diagnostics.

## Network Health Overview Card

A glance card showing all network metrics at once:

```yaml
type: glance
title: Network Health
entities:
  - entity: sensor.network_diagnostics_gateway_latency
    name: Gateway
  - entity: sensor.network_diagnostics_gateway_jitter
    name: Jitter
  - entity: sensor.network_diagnostics_packet_loss
    name: Loss
  - entity: sensor.network_diagnostics_isp_latency
    name: ISP
  - entity: sensor.network_diagnostics_dns_latency
    name: DNS
```

## Latency History Graph

Track latency over time with a history graph:

```yaml
type: history-graph
title: Network Latency (24h)
hours_to_show: 24
entities:
  - entity: sensor.network_diagnostics_gateway_latency
    name: Gateway
  - entity: sensor.network_diagnostics_isp_latency
    name: ISP
  - entity: sensor.network_diagnostics_dns_latency
    name: DNS
```

## Network Status with Gauges

Visual gauges for key metrics:

```yaml
type: vertical-stack
cards:
  - type: gauge
    entity: sensor.network_diagnostics_gateway_latency
    name: Gateway Latency
    min: 0
    max: 100
    severity:
      green: 0
      yellow: 20
      red: 50
  - type: gauge
    entity: sensor.network_diagnostics_packet_loss
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
name: Network Latency
entities:
  - entity: sensor.network_diagnostics_gateway_latency
    name: Gateway
    color: "#4CAF50"
  - entity: sensor.network_diagnostics_isp_latency
    name: ISP
    color: "#2196F3"
  - entity: sensor.network_diagnostics_dns_latency
    name: DNS
    color: "#FF9800"
hours_to_show: 6
points_per_hour: 12
line_width: 2
show:
  labels: true
  points: false
```

## Entities Card with Conditional Formatting

Show status with automatic coloring:

```yaml
type: entities
title: Network Diagnostics
entities:
  - entity: sensor.network_diagnostics_gateway_latency
    secondary_info: last-updated
  - entity: sensor.network_diagnostics_gateway_jitter
  - entity: sensor.network_diagnostics_packet_loss
  - entity: sensor.network_diagnostics_isp_latency
  - entity: sensor.network_diagnostics_dns_latency
  - type: divider
  - entity: button.network_diagnostics_refresh_diagnostics
    name: Refresh Now
```

## Conditional Card for Alerts

Show a card only when there are issues:

```yaml
type: conditional
conditions:
  - entity: sensor.network_diagnostics_packet_loss
    state_not: "0.0"
card:
  type: markdown
  content: >
    ## Network Issues Detected

    Packet loss: {{ states('sensor.network_diagnostics_packet_loss') }}%

    Gateway latency: {{ states('sensor.network_diagnostics_gateway_latency') }}ms
```

## Network Path Visualization

A markdown card showing the network path:

```yaml
type: markdown
title: Network Path
content: >
  ```
  [HA] ──{{ states('sensor.network_diagnostics_gateway_latency') }}ms──> [Gateway]
       ──{{ states('sensor.network_diagnostics_isp_latency') }}ms──> [ISP]
       ──{{ states('sensor.network_diagnostics_dns_latency') }}ms──> [DNS]
  ```

  **Packet Loss:** {{ states('sensor.network_diagnostics_packet_loss') }}%

  **Jitter:** {{ states('sensor.network_diagnostics_gateway_jitter') }}ms
```

---

## Screenshots

*Screenshots will be added after initial testing*

![Dashboard Overview](../images/dashboard-placeholder.png)
