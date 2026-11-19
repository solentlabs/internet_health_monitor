# Internet Health Monitor Core

The measurement engine behind the Internet Health Monitor Home Assistant
integration, usable on its own. It finds the gateway and the first three
hops toward the internet, then reports per-hop latency, jitter and packet
loss, plus DNS latency. It has no Home Assistant dependency.

Runs on Linux and Windows. On Linux it calls `ip`, `ping` and
`traceroute`. On Windows it calls the IP Helper API directly, so
it needs no extra tools and no admin rights; Windows reports round-trip
times in whole milliseconds, so a sub-millisecond gateway reads 0 or 1 ms.

## Command line

```bash
pip install solentlabs-internet-health-monitor-core

internet-health-monitor                 # one poll, one JSON line
internet-health-monitor --interval 60   # one JSON line per poll until stopped
```

| Option | Default | Meaning |
|--------|---------|---------|
| `--dns-server` | `auto` | DNS server to time; `auto` reads `/etc/resolv.conf` |
| `--ping-count` | 3 | Pings per target per poll (1 to 10) |
| `--interval` | none | Seconds between polls (up to 3600, and at least as long as a poll can take: 5 s per ping per target). Without it, one poll and exit. The HA integration uses 60 |
| `--hop-ownership` | off | Add each public hop's network operator; sends those hop addresses to Team Cymru |

Jitter is the spread of latency across polls, so a single poll reports
none; use `--interval` to get it.

## Library

```python
from solentlabs.internet_health_monitor_core.network_diagnostics import (
    NetworkDiagnostics,
)

result = await NetworkDiagnostics().run_diagnostics()
print(result.to_dict())
```

Licence: MIT.
