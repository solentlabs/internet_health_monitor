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
internet-health-monitor --speed-test cloudflare   # one speed test, one JSON line
```

| Option | Default | Meaning |
| -------- | --------- | --------- |
| `--dns-server` | `auto` | DNS server to time; `auto` reads `/etc/resolv.conf` |
| `--ping-count` | 3 | Pings per target per poll (1 to 10) |
| `--internet-reference` | `1.1.1.1` | Public IPv4 address pinged each poll as a reading past your ISP, like a hop, or `off` |
| `--interval` | none | Seconds between polls (up to 3600, and at least as long as a poll can take: 5 s per ping per target). Without it, one poll and exit. The HA integration uses 60 |
| `--hop-ownership` | off | Add each public hop's network operator; sends those hop addresses to Team Cymru |
| `--speed-test` | none | Run one speed test with `cloudflare`, `mlab` or `librespeed`, print it, and exit. The service sees your public IP address |
| `--data-limit` | 500 | Most MB one speed test may use, both directions together (100 to 10000); each direction stops at half |
| `--mlab-consent` | off | Required with `--speed-test mlab`: M-Lab publishes every result with your public IP address, permanently |

M-Lab asks each client for at most 40 tests a day, and at most 4 automated
ones at random times. Run from cron or a script (no terminal on standard
input), `--speed-test mlab` counts as automated and first waits a random time
of up to an hour; runs past either limit are refused. Runs are recorded in
`internet-health-monitor/mlab_runs.json` in your state directory
(`~/.local/state`, or `%LOCALAPPDATA%` on Windows).

Jitter is the mean change between consecutive ping round trips within a
poll, so it needs `--ping-count` of 2 or more. Speed test services and
their terms: [docs/SPEED_TEST_BACKENDS.md](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/SPEED_TEST_BACKENDS.md).

## Library

```python
from solentlabs.internet_health_monitor_core.network_diagnostics import (
    NetworkDiagnostics,
)

result = await NetworkDiagnostics().run_diagnostics()
print(result.to_dict())

# Speed test: pass your own aiohttp session; failures raise SpeedTestError.
import aiohttp
from solentlabs.internet_health_monitor_core.data_plan import automatic_limit
from solentlabs.internet_health_monitor_core.speed_test import DataLimit, run_speed_test

async with aiohttp.ClientSession() as session:
    speed = await run_speed_test("cloudflare", session, DataLimit.even(500))  # 250 MB each way
    # The next test sized from this one, as Home Assistant's automatic limit is:
    again = await run_speed_test("cloudflare", session, automatic_limit(speed))
print(speed.bufferbloat_grade, speed.download_ended_by, speed.upload_ended_by)
```

A result also gives each direction's latency increase under load and a
bufferbloat grade on Waveform's scale (`bufferbloat.py`); `data_plan.py`
holds the rules that size a test and space automatic ones.

License: MIT.
