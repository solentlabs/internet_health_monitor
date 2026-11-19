# Speed Test Backends

Which service runs your speed test, what each choice means for you, and
how IHM measures. Decision:
[ARCHITECTURE_DECISIONS.md § ADR-003](ARCHITECTURE_DECISIONS.md#adr-003-speed-testing-with-user-selected-backends).
Sources and evidence labels: [REFERENCES.md](REFERENCES.md) R5, R9, R19,
R20. IHM keeps to each provider's published terms as closely as it can;
where terms are silent, it uses the provider the way the provider's own
client does.

Speed tests are off until you pick a backend. IHM is not affiliated with
any of these providers.

## At a Glance

| Backend | Loaded latency | Who sees your public IP address | Limits |
|---------|----------------|----------------------------------|--------|
| **Cloudflare** | Yes, per direction | Cloudflare; it keeps the address cut to /24 (IPv4) or /48 (IPv6) *(unverified)* | None published; IHM's limits apply |
| **M-Lab NDT7** | Server's view of round-trip time; download good, upload approximate | **M-Lab publishes it with every result, permanently** | 4 automated a day at random times; 40 a day in all |
| **LibreSpeed** | Yes, per direction | The volunteer server you are matched with | None published; IHM's limits apply |
| Fast.com | Not offered: Netflix's terms forbid automated access to its websites ([below](#why-not-fastcom)) | | |
| Ookla | Not offered: personal, non-commercial license, which IHM won't accept for you | | |
| Self-hosted server | Not offered: IHM never requires running a server | | |

Every speed test, with any provider, shows the provider your public IP
address: the test is a connection from your network to theirs.

## What a Test Measures

Every backend returns the same result (Core `speed_test.SpeedTestResult`):

| Field | Meaning |
|-------|---------|
| Download, upload | Mbit/s of test data received or sent. No overhead factor is added, so it reads a few percent below the line rate that includes TCP/IP headers |
| Idle latency | Median round trip before any load |
| Download latency, upload latency | Median round trip while that direction is loaded. Minus idle latency, this is bufferbloat |
| Data used | Megabytes of test data, both directions, so you can budget a data cap |
| Server | Which server ran the test |

A test that fails returns no numbers: the speed test sensors go
unavailable and the Run speed test button reports why. Nothing reads 0
because a test failed. The failure still reports the data the test
moved before it stopped (received, or handed to the network to send),
and IHM's usage totals include it.

## How IHM Measures

One engine serves the HTTP backends; NDT7 follows M-Lab's protocol.

**HTTP backends** (Cloudflare, LibreSpeed):
1. **Idle latency:** 10 small requests one after another, after one
   warm-up; the median time to the first response byte. Cloudflare
   reports its own processing time in a `server-timing` header, which is
   subtracted (R5).
2. **Download:** 4 parallel streams, each fetching large chunks
   back to back, for 10 s. The first 1.5 s is excluded while TCP ramps
   up; throughput is the bytes received after that, over the time after
   that.
3. **Upload:** the same, with 4 streams posting chunks.
4. **Loaded latency:** during each direction, a small request every
   0.4 s on its own connection (Cloudflare's spacing, R5); the median.

**M-Lab NDT7** (R9): the Locate API picks the nearest server; the
download and upload run over a WebSocket for up to 10 s each, as the
ndt7 protocol specifies. Download throughput is bytes received over
elapsed time, the method of M-Lab's own client. Upload throughput is the
byte count the server reports, which excludes data still queued on the
sending side. Idle latency is the server kernel's minimum round-trip
time; loaded latency is the median of its smoothed round-trip time
during each direction.

**Every backend** identifies itself as `internet-health-monitor/<version>`
in its User-Agent (and, for M-Lab, as `client_name`), sends nothing to a
results or telemetry endpoint, and gives up after 60 s.

## Running Tests and Limits

Tests never run on their own. They run when you press **Run speed
test**, or when an automation presses it: HA's quality rules bar an
integration from offering its own polling schedule (R16), and an
automation can test at any time or condition you like (README.md §
Speed Testing).

Two settings bound the cost, counting every run, failed ones included:

| Setting | Default | Range | Why |
|---------|---------|-------|-----|
| Data limit per test | 1000 MB | 100 to 10000 MB | Each direction stops at half, so a fast line cannot use a large share of a data cap |
| Tests per day | 4 | 1 to 40 | Any 24 hours. 4 is M-Lab's limit for automated clients; 40 its limit for interactive users (R9) |

With M-Lab, IHM also follows its rules for automated clients (R9). A
press with no person behind it (an automation or script) counts toward
at most 4 a day, whatever Tests per day says. It starts after a random
wait of up to an hour, so homes running the same automation do not test
at the same moment; the press returns at once and the sensors update
when the test finishes. M-Lab asks for randomized times without naming
a window; one hour is IHM's choice. A person's press runs at once.

## Data Use

A 10 s test in each direction moves roughly 10 s × your line speed:
about 125 MB down on a 100 Mbit/s line, 1.25 GB on a 1 Gbit/s line,
plus the upload. Each result reports the exact amount (Data used).

## Backends

### Cloudflare

- **Choose it if** you want per-direction loaded latency from a large
  network, without your result being published.
- **Privacy:** Cloudflare keeps an anonymized result; its speed test
  says it truncates your address before storing it *(unverified, R5)*.
  IHM does not post to Cloudflare's results endpoint (R5).
- **Terms:** Cloudflare's website terms bar use that could "overburden"
  its servers or that "violates any Cloudflare documentation" (R5). IHM
  calls the endpoints as Cloudflare's own published client does, within
  your limits. Their automated-access clause covers only AI training
  (R5). No permission was sought.

### M-Lab NDT7

- **Choose it if** you want the provider that publicly welcomes
  automated tests and don't mind your results being public.
- **Privacy:** M-Lab publishes every result, including your public IP
  address, date and time, and keeps it indefinitely (R9). M-Lab requires
  informed consent, so IHM asks you to confirm this before saving the
  choice.
- **Limits:** M-Lab asks automated clients for no more than 4 tests a
  day at random times, and interactive users for no more than 40 (R9);
  IHM enforces both ([Running Tests and Limits](#running-tests-and-limits)).
- **Latency:** NDT7 has no separate latency test; the server's
  round-trip readings stand in, and upload latency may be unreliable.

### LibreSpeed

- **Choose it if** you prefer an open-source project with community
  servers.
- **Server:** IHM fetches LibreSpeed's public server list and uses the
  one that answers fastest (R20).
- **Privacy:** the server's operator sees your address. IHM sends no
  telemetry; LibreSpeed's own website does (R20).
- **Terms:** none published for the public servers (R20); your limits
  keep use modest.

## Why Not Fast.com

Fast.com is Netflix's speed test, and HA core ships an integration for
it, so its absence is deliberate:

- Netflix's Terms of Use forbid "any robot, spider, scraper or other
  automated means to access the Netflix service", and define that
  service to include Netflix's websites (R19).
- Fast.com publishes no API. Every client, HA core's included, reads an
  access token out of fast.com's own page: automated access to a
  Netflix website.
- IHM keeps to providers' terms as closely as it can (ADR-003). Written
  permission from Netflix would let it return as one module.

## Passive Bufferbloat, Without a Speed Test

First-ISP-hop latency rising while gateway latency stays flat points to
a queue past your router
([ARCHITECTURE_DECISIONS.md § ADR-001](ARCHITECTURE_DECISIONS.md#adr-001-bufferbloat-is-measured-passively-in-ihm)).
It needs no backend and uses almost no data.

## Adding a Backend

One module in Core's `backends/` implementing `SpeedTestBackend`, one
entry in `speed_test.BACKENDS`, tests against an in-process fake of the
provider, and a row in each table here and in
[ARCHITECTURE.md § Data Leaving the Host](ARCHITECTURE.md#data-leaving-the-host).
HTTP providers reuse the shared engine by describing their URLs.
