# Internet Health Monitor for Home Assistant

<!-- Versions & Install -->
[![GitHub Release](https://img.shields.io/github/v/release/solentlabs/internet_health_monitor?include_prereleases)](https://github.com/solentlabs/internet_health_monitor/releases)
[![Core](https://img.shields.io/pypi/v/solentlabs-internet-health-monitor-core?label=core)](https://pypi.org/project/solentlabs-internet-health-monitor-core/)
[![HA analytics installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=HA%20analytics&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.internet_health_monitor.total)](https://analytics.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<!-- Build Status -->
[![Tests](https://github.com/solentlabs/internet_health_monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/solentlabs/internet_health_monitor/actions/workflows/tests.yml)
[![CodeQL](https://github.com/solentlabs/internet_health_monitor/actions/workflows/codeql.yml/badge.svg)](https://github.com/solentlabs/internet_health_monitor/actions/workflows/codeql.yml)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

<!-- Meta -->
[![AI Assisted](https://img.shields.io/badge/AI-Claude%20Assisted-5A67D8.svg)](https://claude.ai)

A **Solent Labs** Home Assistant integration for comprehensive internet health monitoring with multi-hop network path visibility.

![Internet Health dashboard card](https://raw.githubusercontent.com/solentlabs/internet_health_monitor/main/images/dashboard-screenshot-dark.png)

> **⭐ If you find this integration useful, please star this repo!**
> It helps others find the project.
>
> **🤖 AI-Assisted Development**: This project uses AI-assisted development (Claude) to accelerate implementation while maintaining human oversight for architecture and community decisions.

## Features

- **Network path, hop by hop** - Latency, jitter and packet loss for hop 1 (your gateway), hop 2 (usually your ISP's first router) and hop 3, so you can see where a problem starts
- **Internet reference** - The same three readings for a well-known address past your ISP (Cloudflare's 1.1.1.1 by default, or one you pick), so you can tell a problem at home, on your line, or beyond it
- **DNS latency** - One uncached lookup per poll at the DNS server you choose
- **Reachability** - Gateway reachable and internet reachable binary sensors
- **Speed tests you control** (optional) - Cloudflare, M-Lab or LibreSpeed; whole tests spaced to fit your data budget, with the working shown
- **Bufferbloat** - Graded A+ to F on Waveform's scale from each speed test, and visible between tests as hop 2 rising over a flat gateway
- **Zero configuration** - Gateway, hops and DNS server are detected automatically
- **Dashboard card** - Pick Internet Health in Add card; set it up in a form, no YAML

### What Makes This Different

| Feature | Other Solutions | Internet Health Monitor |
| --------- | ----------------- | ------------------------ |
| Gateway detection | Manual config | Auto-detected |
| Path visibility | Single target only | Hops 1 to 3, each with its own sensors |
| DNS latency | Cache-affected | Uncached query to your chosen DNS server |
| Configuration | YAML editing | UI setup |

## Installation

### Marketplace

The Marketplace is built into Home Assistant 2026.11 and later; on
2026.10, use [HACS](https://www.hacs.xyz/docs/use/download/download/) the
same way. Internet Health Monitor is in beta and not yet in the
Marketplace's list, so add it as a custom repository first:

1. Open **Settings → Marketplace**, then the **⋮** menu → **Custom
   repositories**.
2. Add `https://github.com/solentlabs/internet_health_monitor`, type
   **Integration**.
3. Open **Internet Health Monitor** and install it, as a beta below.
4. Restart Home Assistant, then go to **Settings → Devices & services →
   Add integration** and search for **Internet Health Monitor**.

### Testing a Beta Release

Betas are opt-in. Pre-releases stay hidden until you turn them on, and
you install each beta yourself.

1. Open **Settings → Marketplace → Internet Health Monitor**.
2. Click the **⋮** menu → **Include pre-releases** and confirm.
3. Click the **⋮** menu → **Install another version**.
4. Pick the beta from the list. Betas are labeled **Pre-release**.
5. Click **Install** and restart Home Assistant if prompted.

To leave the beta channel, click the **⋮** menu → **Exclude
pre-releases**; the next stable release then arrives as a normal update.

In HACS on Home Assistant 2026.10, open **Internet Health Monitor**, click
the **⋮** menu → **Redownload**, turn on **Show beta versions**, pick the
beta, then **Download**.

### Removal

1. Go to Settings > Devices & Services > Internet Health Monitor
2. Open the menu (three dots) and select Delete
3. Uninstall it in the Marketplace (or HACS), then restart Home Assistant

## Configuration

During setup, and later under Configure, you can set:

| Option | Default | Description |
| -------- | --------- | ------------- |
| DNS server | Auto-detect | Server to time: auto-detect uses the one this host is configured with (on HA OS and Supervised, the host's own server, which the Supervisor reports); pick a public one from the list, or type any IPv4 or IPv6 address, such as a Pi-hole's. The DNS latency sensor's `dns_source` attribute says where it came from |
| Pings per target | 3 | Pings sent to each target per poll (1 to 10) |
| Internet reference | Cloudflare (1.1.1.1) | An address past your ISP, pinged each poll like a hop. Pick Google, Quad9 or OpenDNS, type any public IPv4 address, or choose Off. See [Internet Reference](#internet-reference) |
| Look up who runs each hop | off | Adds each public hop's network operator; sends hop addresses to Team Cymru. See [Hop Ownership](#hop-ownership) |
| Usage totals | off | Adds six sensors counting what IHM has sent. See [Usage Totals](#usage-totals) |
| Long-term statistics | off | Keeps hourly statistics of latency, jitter, loss and speed tests for trends over months; Home Assistant never deletes them, so they add about 10 to 15 MB a year. Off, history covers the last 10 days. See [Database Space](#database-space) |
| Speed test service | Off | Cloudflare, M-Lab NDT7 or LibreSpeed. See [Speed Testing](#speed-testing) |

Choosing a speed test service adds a second screen:

| Option | Default | Description |
| -------- | --------- | ------------- |
| Automatic tests | on | At a random time from 1 to 5 am: weekly with no data budget, or as often as the budget holds every test |
| Data limit per test | 0 (automatic) | Sized from the last test's speeds; or 100 to 10000 MB, both directions together |
| Daily test limit | 4 | A cap, not a schedule: most tests in any 24 hours, every kind counted (1 to 40) |
| Data budget per 30 days | 0 (none) | Sets how often automatic tests run; a test starts only if its data limit fits what is left (0 to 10000 GB) |

The screen shows its working: the last test's speeds, what each test may
use, the days between automatic tests, and the most they can use in any
30 days. See [How Much Data Speed Tests Use](#how-much-data-speed-tests-use).

The gateway, the three hops and DNS are always measured: they are what
IHM is for, and they never reach beyond your ISP and DNS server. The
internet reference is the one probe you can turn off. Off removes its
three sensors and sends it no pings; choosing a provider again recreates
them with the same ids, and their history returns.

### Internet Reference

The three hops show where a slowdown starts at home (hop 1) or on your
line (hop 2). The internet reference adds a point past your ISP: an
address built to answer pings, whose address does not move. Read the
four together: if only the reference rises, the problem is beyond your
line.

It is on by default, pinging Cloudflare's 1.1.1.1 with the same number
of pings as each hop (3 a minute by default). Cloudflare sees your public
IP address, as with any ping. IHM chose Cloudflare because its terms
cover the 1.1.1.1 resolver and limit only use that would overburden it;
Quad9's and OpenDNS's current terms could not be found
([ADR-015](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/ARCHITECTURE_DECISIONS.md#adr-015-internet-reference-ping-on-by-default-to-cloudflare)).
A typed address must be a public IPv4 address. The traceroute also aims
at the reference, so hops 1 to 3 lie on the path to it.

### Polling

IHM polls every 60 seconds, in line with comparable monitors
([ADR-007](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/ARCHITECTURE_DECISIONS.md#adr-007-fixed-60-second-polling)). For a different interval, open the integration's
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
          entity_id: sensor.internet_health_dns_latency
```

Updating any one IHM entity runs a full poll for all of them.

### Renaming

Every entity starts with the device name, "Internet Health", so a new
install creates ids like `sensor.internet_health_hop_2_latency_isp`. To
use your own prefix, go to Settings > Devices & services > Devices, open
**Internet Health**, select the pencil icon, enter a new name (for example
"Network"), and accept the offer to rename the entity ids. You get
`sensor.network_hop_2_latency_isp`, and the names on your dashboards follow.
There is no prefix setting: Home Assistant asks integrations to leave naming
to this screen
([ADR-010](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/ARCHITECTURE_DECISIONS.md#adr-010-names-are-changed-by-renaming-the-device)).

### Hop Ownership

Off by default. When on, each hop sensor gains `asn` and `as_name`
attributes naming the network that runs that hop, for example
`15169` / `GOOGLE - Google LLC, US`.

| | |
| --- | --- |
| **What you get** | Whose network a hop belongs to: useful evidence when you report a problem to your ISP, and it works when a router has no hostname. |
| **What is sent** | Each public hop address to Team Cymru's free IP-to-ASN service, as a DNS query through your DNS server. These are your ISP's routers, never your own address. Looked up once when hops are detected, not every poll. |
| **What it often can't do** | Many ISPs use private (`10.x`) or shared (`100.64.x`) addresses on their first routers. Those have no owner, are never sent, and show no `asn`. On such a connection the option finds nothing in hops 1 to 3. |
| **Accuracy** | A router where two networks meet may carry the other network's address, so it can be labelled with the neighboring operator. |
| **Not included** | Location. IP location data is unreliable for routers, and Team Cymru asks that the service not be used for it. Router hostnames often name the city anyway. |

## Entities

### Sensors

Three per hop, for hops 1 (gateway), 2 (usually your ISP's first router) and 3 (the router after it), three for the internet reference, plus DNS and two about the host:

| Sensor | Unit | Description |
| -------- | ------ | ------------- |
| Hop N latency | ms | Average round-trip time ping reported for this hop |
| Hop N jitter | ms | Average change between consecutive ping round-trip times in this poll, as speed test sites measure it |
| Hop N packet loss | % | Share of this poll's pings to the hop with no reply |
| Internet latency, jitter, packet loss | ms, ms, % | The same three readings for the internet reference (attribute `reference_ip`). Not created when it is Off |
| DNS latency | ms | Time for one uncached lookup at the DNS server |
| Connection type | | Ethernet, Wi-Fi, Bridge or Virtual Ethernet, from the name of the interface the default route uses (attribute `interface`). Diagnostic |
| Install type | | How Home Assistant is installed, as HA reports it: Home Assistant OS, Supervised, Container, Core or Third-party container. Diagnostic |
| Speed test download, upload | Mbit/s | Test data received or sent per second in the latest test. With a speed test service only |
| Speed test idle latency | ms | Median round trip before the test loads the line |
| Speed test download latency, upload latency | ms | Median round trip while that direction is loaded |
| Speed test data used | MB | Data the latest test used, both directions |
| Speed test download latency increase, upload latency increase | ms | Loaded minus idle latency in that direction: bufferbloat. See [Bufferbloat](#bufferbloat) |
| Speed test bufferbloat grade | | A+ to F on Waveform's scale, from the larger of the two increases |

Hop sensors carry attributes: `hop_ip`, `reachable`, `address_type`
(`private` for a home or internal block, `shared` for ISP-internal
carrier-grade NAT space `100.64.x`, `public` for an internet address,
from the address itself), `packets_sent`, `packets_received`,
`hostname` (when the hop has one) and, with hop
ownership on, `asn` and `as_name`. Speed test sensors carry `backend`,
`server` and `tested_at`; download and upload also carry `ended_by`
(`time`, or `data_limit` when the limit stopped that direction early) and
`duration_s`, the seconds it was loaded; the bufferbloat grade carries
`latency_increase_ms`, the larger increase it was read from. DNS
latency carries `dns_server`, `success` and `dns_source`: `chosen`
(picked in the options), `host` (the host's own server, from the
Supervisor), `system` (this system's `/etc/resolv.conf`) or `fallback`
(none found, so 1.1.1.1). The measurement sensors keep
long-term statistics only with the *Long-term statistics* option on.

### Database Space

Home Assistant keeps 10 days of every sensor's history, then deletes it.
IHM's share holds at about 15 to 25 MB, depending on the options below,
and does not grow.

Only *Long-term statistics* grows the database, because Home Assistant
never deletes statistics:

| Long-term statistics | Added per year |
| -------------------- | -------------- |
| Off (default) | Nothing |
| On | About 10 MB |
| On, with a speed test service | About 14 MB |
| On, with the internet reference Off | About 7.5 MB, or 12 MB with a speed test service |

Figures are for Home Assistant's default SQLite database; MariaDB and
PostgreSQL differ somewhat. Pings per target, the DNS server and hop
ownership do not change them. `scripts/dev/measure_recorder_size.py`
reproduces them ([REFERENCES.md § R28](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/REFERENCES.md#r28-database-space-measured)).

### Usage Totals

What IHM has sent since it was installed, so you can see what monitoring
costs your network. Turn on *Usage totals* under Configure to add these
six diagnostic sensors; turning it off removes them. IHM counts either
way, so they show everything since install. They count up across
restarts and reset only when the integration is removed.

They keep no long-term statistics, which Home Assistant never deletes.
Home Assistant still records their recent changes (10 days by default).
To keep only the totals, exclude them from the recorder in
`configuration.yaml`:

```yaml
recorder:
  exclude:
    entities:
      - sensor.internet_health_pings_sent
      - sensor.internet_health_traceroutes_run
      - sensor.internet_health_dns_queries_sent
      - sensor.internet_health_speed_tests_run
      - sensor.internet_health_speed_test_data_downloaded
      - sensor.internet_health_speed_test_data_uploaded
```

| Sensor | Unit | Counts |
| -------- | ------ | -------- |
| Pings sent | pings | Every ping to the gateway, the hops and the internet reference |
| Traceroutes run | traceroutes | Each hop detection: at start, when the gateway changes, every 10 minutes while hops are missing, and after a cache reset |
| DNS queries sent | queries | Latency probes, reverse lookups of hops, and hop ownership queries |
| Speed tests run | tests | Every speed test started, failed ones included |
| Speed test data downloaded, uploaded | MB | Data moved by every speed test, including data a failed test moved before it stopped |

### Binary Sensors

| Sensor | On when |
| -------- | --------- |
| Gateway reachable | The gateway answers a ping |
| Internet reachable | A DNS lookup succeeds |

A failure turns a sensor off only after two quick re-checks, 5 s apart,
also fail, so one lost packet never shows as an outage. While off, IHM
re-checks every 10 s, so recovery shows within about 10 s. While
everything answers, nothing extra runs between polls.

### Buttons

| Button | Description |
| -------- | ------------- |
| Refresh diagnostics | Poll now instead of waiting for the next poll |
| Reset network cache | Forget the detected gateway, hops, hostnames and DNS server and detect them again. IHM re-detects on its own when the gateway changes or hops are missing; this forces it. Disabled by default |
| Run speed test | Run one speed test now. A press while a test runs, such as a double click, is ignored and uses none of the allowance. When you press it yourself, a notification gives the result. With a speed test service only |

## Speed Testing

Optional, and off until you choose a service under Configure. Each
test measures download, upload, latency at rest and latency while each
direction is loaded (the difference is bufferbloat), plus the data the
test used.

| Service | Loaded latency | Who sees your public IP address |
| --------- | ---------------- | ---------------------------------- |
| Cloudflare | Per direction | Cloudflare, which says it truncates it to /24 (IPv4) or /48 (IPv6) |
| M-Lab NDT7 | Download good, upload approximate | **M-Lab publishes it with every result, permanently**; you confirm this before first use |
| LibreSpeed | Per direction | The volunteer server you are matched with |

Every speed test shows the service your public IP address. Each
option's description says so before you turn it on. IHM keeps to each
provider's terms, which is why Fast.com and Ookla are not offered.
IHM is not affiliated with any of these providers. Details, methods and
the reasons: [docs/SPEED_TEST_BACKENDS.md](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/SPEED_TEST_BACKENDS.md).

**Running tests.** *Automatic tests* run at a random time from 1 to
5 am, when a test is least likely to slow a call or a game: weekly with
no data budget, or as often as the budget holds every test (see below).
Press **Run speed test** for one now; the card asks first, and a
notification gives the result. Automatic tests and automations stay
silent: their results are on the sensors. For other times, turn automatic
tests off and use an automation; this one tests at 6 pm with a random
delay, so homes don't all test at once:

```yaml
alias: Evening speed test
triggers:
  - trigger: time
    at: "18:00:00"
actions:
  - delay:
      minutes: "{{ range(0, 60) | random }}"
  - action: button.press
    target:
      entity_id: button.internet_health_run_speed_test
```

IHM cannot tell when your household is busy, so a test, automatic or
not, can briefly slow other traffic.

**Limits.** *Daily test limit* (default 4, up to 40) counts every run in
any 24 hours. *Data budget per 30 days* is off by default; if your plan
has a data cap, set it to a small share of it. A test starts only if its
data limit fits what is left, so the budget is never exceeded. With
M-Lab, a run no person started (an automatic test or an automation)
counts toward at most 4 a day, and one an automation started waits a
random time of up to an hour, as M-Lab asks; a run you start yourself
goes at once.

A failed test makes the speed test sensors unavailable and the button
shows why; nothing reads 0 because a test failed. The last result
survives a restart.

### How Much Data Speed Tests Use

A few whole tests a month say more than many cut short, so IHM sizes
each test to finish and spaces tests to fit your budget:

1. **A full test** loads each direction for 10 seconds, so it moves
   about 1.25 MB for every Mbit/s of download plus upload.
2. **The automatic data limit** (*Data limit per test* 0, the default)
   gives each direction what 10 seconds at the last test's speed used,
   plus 25%, so a line up to a quarter faster still gets a whole test.
   Each direction is at least 50 MB. The first test, with nothing to go
   on, uses 500 MB, split evenly. A limit you set yourself is split
   evenly, and on a fast line it can stop a direction early.
3. **Never past the budget.** An automatic limit larger than the whole
   budget is cut to fit it, keeping the slower direction whole.
4. **Spacing.** With no budget, automatic tests run weekly. With one,
   IHM counts how many tests at their limit the budget holds and spaces
   them so no 30 days hold more, allowing for the 4-hour start window
   and a clock change. So the budget never refuses an automatic test.
5. **You see it.** The setup screen shows the working, and each
   download and upload reading says whether time or the data limit
   ended it (`ended_by`).

<!-- Generated from Core's data_plan.py; tests/components/test_docs.py checks it. -->
| Line (Mbit/s down/up) | A full test uses | Automatic limit | No budget | 10 GB budget | 50 GB budget |
| --- | --- | --- | --- | --- | --- |
| 100/10 | about 140 MB | 210 MB | weekly | daily | daily |
| 300/20 | about 400 MB | 520 MB | weekly | every 2 days | daily |
| 1000/40 | about 1300 MB | 1640 MB | weekly | every 6 days | every 2 days |
| 2000/100 | about 2620 MB | 3290 MB | weekly | every 11 days | every 3 days |

A 1000/40 line tested weekly uses about 1.3 GB a week; tested daily it
would use about 39 GB in 30 days. The exact rules: [docs/SPEED_TEST_BACKENDS.md § Data Use](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/SPEED_TEST_BACKENDS.md#data-use).

### Bufferbloat

Bufferbloat is delay that builds up when a busy link queues traffic: a
video call stutters while someone uploads photos. Each speed test
measures latency at rest and while each direction is loaded; the
difference is the **latency increase**, one sensor per direction. The
**bufferbloat grade** reads the larger increase on
[Waveform's published scale](https://www.waveform.com/tools/bufferbloat),
as Waveform grades its own test:

| Grade | Latency increase |
| ------- | ------------------ |
| A+ | under 5 ms |
| A | under 30 ms |
| B | under 60 ms |
| C | under 200 ms |
| D | under 400 ms |
| F | 400 ms or more |

Waveform: "Anything worse than a B may affect video calls, gaming, and
other real-time applications." IHM's loaded latency is the median of
probes after the first 1.5 seconds of load
([docs/SPEED_TEST_BACKENDS.md § How IHM Measures](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/SPEED_TEST_BACKENDS.md#how-ihm-measures));
noise can make an increase slightly negative, which grades A+. The two
increase sensors show which direction set the grade.

Between tests, hop latency shows bloat for free: hop 2 rising while the
gateway stays flat points to a queue past your router
([ADR-001](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/ARCHITECTURE_DECISIONS.md#adr-001-bufferbloat-is-measured-passively-in-ihm)).

```yaml
type: entities
title: Bufferbloat
entities:
  - entity: sensor.internet_health_speed_test_bufferbloat_grade
    name: Grade
  - entity: sensor.internet_health_speed_test_download_latency_increase
    name: Download increase
  - entity: sensor.internet_health_speed_test_upload_latency_increase
    name: Upload increase
```

## Network Path Visualization

```text
[HA Host] ─Hop 1─> [Gateway] ─Hop 2─> [ISP Router] ─Hop 3─> [Next Router] ─DNS─> [DNS Server]
           1.2ms      │         15ms       │          25ms         │        35ms
                      └── Packet Loss ─────┴── Jitter ─────────────┘
```

## Dashboard Card

IHM ships its own card. Edit a dashboard, choose **Add card**, and pick
**Internet Health**. If it is missing right after installing, refresh
the browser: it learns of the card when the page loads.

| Option | Default | Shows |
| -------- | --------- | ------- |
| Network status | on | Gateway and internet reachable, DNS latency, Refresh diagnostics |
| Each hop | on | A card per hop (Gateway, ISP, Hop 3), then one for the internet reference, each with its current latency, jitter and packet loss, and its address |
| Latency graphs | on | Latency history for the hops and the internet reference, and DNS latency on its own graph |
| Jitter graph | on | Jitter history for the hops and the internet reference |
| Packet loss graph | on | Packet loss history for the hops and the internet reference |
| Speed test | on | Each speed test reading but data used (see Usage totals for the running total); Run speed test, which asks before it starts; bufferbloat gauges colored at Waveform's B line (the grade full width, download and upload in ms below it), each shown once a speed test has measured it; and a throughput graph. Shown only with a speed test service |
| Graph hours | 24 | Hours each graph shows (1 to 168) |

**Want a different order or layout?** The card's form shows and hides
parts but keeps their order. To reorder sections or change anything
else, generate the card as YAML and edit it: see
[Your Own Order or Layout](#your-own-order-or-layout).

Each measurement has its own row or line; there is no combined score
([ADR-004](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/ARCHITECTURE_DECISIONS.md#adr-004-no-composite-health-sensors)).
Disabled entities, and those of monitoring you turned off, are left out.
Titles and row names are in English; a name you give an entity replaces its row name. If the card fails to load, monitoring is
unaffected. Design: [docs/DASHBOARD_CARD.md](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/DASHBOARD_CARD.md).

The reachable sensors are connectivity sensors, and HA colors any binary
sensor that is on in amber. The card keeps your theme's colors. For
green, add this to your [theme](https://www.home-assistant.io/integrations/frontend/#defining-themes):

```yaml
state-binary_sensor-connectivity-on-color: var(--green-color)
```

### Your Own Order or Layout

The **Generate dashboard card** action gives you the card as YAML, which
you can rearrange freely:

1. Go to **Developer tools > Actions** and choose **Internet Health
   Monitor: Generate dashboard card**.
2. Set the options as you would on the card, then select **Perform
   action**. The response appears below.
3. Copy everything under `yaml: |`. Its indentation is fine as it is.
4. Edit a dashboard, choose **Add card > Manual**, paste, and move the
   sections into the order you want, or delete, retitle and restyle
   them. Each section is one HA card, starting at a `- type:` line.

A pasted card is yours: it keeps its layout when IHM updates, so it will
not pick up new sections or changes from a later release. Generate it
again after an update to see what changed. The Internet Health card from
**Add card** always shows the current layout.

The action is `internet_health_monitor.generate_dashboard_card`. It takes
the options above (`include_status`, `include_hops`, `include_latency`,
`include_jitter`, `include_packet_loss`, `include_speed_test`,
`graph_hours`) and responds with `yaml`. It fails with a message when
IHM is not set up or every part is off.

## Dashboard Examples

Entity ids below are the ones a new install creates. More examples:
[docs/dashboard-examples.md](https://github.com/solentlabs/internet_health_monitor/blob/main/docs/dashboard-examples.md).

### Network Path at a Glance

```yaml
type: glance
title: Network Path
entities:
  - entity: sensor.internet_health_hop_1_latency_gateway
    name: Gateway
  - entity: sensor.internet_health_hop_2_latency_isp
    name: ISP
  - entity: sensor.internet_health_hop_3_latency
    name: Hop 3
  - entity: sensor.internet_health_dns_latency
    name: DNS
```

### Latency History

```yaml
type: history-graph
title: Network Path Latency (24h)
hours_to_show: 24
entities:
  - entity: sensor.internet_health_hop_1_latency_gateway
    name: Gateway
  - entity: sensor.internet_health_hop_2_latency_isp
    name: ISP
  - entity: sensor.internet_health_hop_3_latency
    name: Hop 3
  - entity: sensor.internet_health_dns_latency
    name: DNS
```

### Status Card

```yaml
type: entities
title: Internet Health Monitor
entities:
  - entity: binary_sensor.internet_health_gateway_reachable
  - entity: binary_sensor.internet_health_internet_reachable
  - type: divider
  - entity: sensor.internet_health_hop_1_packet_loss_gateway
  - entity: sensor.internet_health_hop_2_packet_loss_isp
  - entity: sensor.internet_health_hop_2_jitter_isp
  - type: divider
  - entity: button.internet_health_refresh_diagnostics
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
- **Hop 2 is usually, not always, your ISP.** With a second router in
  the home (double NAT, some mesh systems), hop 2 is that router and your
  ISP starts at hop 3. The `address_type` attributes and hop addresses
  show which.
- **Some routers never answer.** A router that ignores traceroute or ping
  leaves its hop unknown or shows 100% loss, even when traffic passes through
  it normally.
- **Jitter needs two replies.** It compares consecutive pings within a poll,
  so with Pings per target set to 1 it is unknown.
- **Auto-detect may time a local relay.** Outside HA OS and Supervised,
  auto-detect reads `/etc/resolv.conf`, which can name a relay on the
  same machine rather than your router or ISP's server: Docker's
  `127.0.0.11` on a custom network, or `127.0.0.53` where
  systemd-resolved runs. DNS latency then includes the relay's hop.
  Check the sensor's `dns_server` and `dns_source` attributes; to time
  the real server, choose it in the options.
- **Fixed 60-second polling** (see [Polling](#polling)).
- **IPv4 only.** IHM measures the IPv4 path. On a dual-stack connection,
  IPv6 traffic may take a different route that IHM does not see.
- **The default route only.** On a host with several network
  connections, IHM measures the one the host's internet traffic uses.
  To watch a specific host, use HA's Ping integration.
- **Hop ownership** finds no owner for private or shared ISP addresses
  (`10.x`, `100.64.x`), which many ISPs use on their first routers, and looks
  up IPv4 hops only.
- **Connection type in a container** is the container's own interface
  unless it uses host networking (HA OS does), so Docker's default bridge
  reads Ethernet even on a Wi-Fi host. Windows hosts report it unknown.

## Troubleshooting

### Setup fails: "Required system tools are missing"

The error names the missing tools. Install them on the Home Assistant host,
then reload the integration. HA OS and the official container include them.

### Hop 2 and 3 sensors show "Unknown"

- `traceroute` is not installed: `sudo apt install traceroute` (Debian/Ubuntu)
  or `apk add traceroute` (Alpine).
- Home Assistant runs in Docker Desktop (Windows or macOS): it hides the
  hops past its own bridge. Run HA on the real network (HA OS, a bridged VM,
  or Docker with host networking on Linux).
- Some routers do not answer traceroute. While hops are missing, IHM traces
  again every 10 minutes, so hops that start answering appear on their own.

### Gateway reachable is off, or no gateway is detected

IHM reads the host's default route every poll, so a router that comes up
after Home Assistant, or a new one, is found within a minute. Check that the
host has one (`ip route show default`).

### Reporting a problem

Attach the diagnostics download (Settings, Devices & services, Internet
Health Monitor, the three-dot menu, Download diagnostics). It includes
IHM's recent log entries, so no log file is needed. Hop hostnames and
public IP addresses are replaced with `**REDACTED**`; private addresses and
each hop's network owner stay. For more detail, turn on debug logging on
the same page, wait for the problem to happen, then download.

## Quality Scale

Home Assistant grades only its built-in integrations against its [Integration Quality Scale](https://contributors.home-assistant.io/core/quality-scale/). This is a self-assessment against the same rules; each rule's status and evidence is in [quality_scale.yaml](https://github.com/solentlabs/internet_health_monitor/blob/main/custom_components/internet_health_monitor/quality_scale.yaml). A tier is reached when all of its rules and every rule below it are met.

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
[packages/internet_health_monitor_core/README.md](https://github.com/solentlabs/internet_health_monitor/blob/main/packages/internet_health_monitor_core/README.md).

## Development

```bash
# Clone the repository
git clone https://github.com/solentlabs/internet_health_monitor.git
cd internet_health_monitor

# Set up development environments (needs uv: https://docs.astral.sh/uv/)
make setup           # .venv: oldest supported HA (2026.10.x), Python 3.14
make setup-current   # .venv-current: newest HA the test harness supports

# Run tests on both HA versions
make test-all

# Run linting
make check
```

## Related Solent Labs Projects

- [Cable Modem Monitor](https://github.com/solentlabs/cable_modem_monitor) - Monitor your cable modem's signal quality, power levels and error rates

## Support

- [GitHub Issues](https://github.com/solentlabs/internet_health_monitor/issues): bugs, with the diagnostics download (see [Reporting a problem](#reporting-a-problem))
- [GitHub Discussions](https://github.com/solentlabs/internet_health_monitor/discussions): questions and ideas

## License

MIT License - see [LICENSE](https://github.com/solentlabs/internet_health_monitor/blob/main/LICENSE) for details. The project's names and logos are not covered by it; see [TRADEMARKS.md](https://github.com/solentlabs/internet_health_monitor/blob/main/TRADEMARKS.md).
