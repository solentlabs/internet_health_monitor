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
| --------- | ---------------- | ---------------------------------- | -------- |
| **Cloudflare** | Yes, per direction | Cloudflare; it says it truncates the address to /24 (IPv4) or /48 (IPv6) (R5) | None published; IHM's limits apply |
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
| ------- | --------- |
| Download, upload | Mbit/s of test data received or sent. No overhead factor is added, so it reads a few percent below the line rate that includes TCP/IP headers |
| Idle latency | Median round trip before any load |
| Download latency, upload latency | Median round trip while that direction is loaded. Minus idle latency, this is bufferbloat |
| Data used | Megabytes of test data, both directions, so you can budget a data cap |
| Ended by, duration | Per direction: `time` if it ran its window (for M-Lab's download, until the server ended it), `data_limit` if its limit stopped it early; and the seconds it was loaded |
| Latency increase | Per direction, loaded minus idle latency: bufferbloat. Noise can make it slightly negative |
| Bufferbloat grade | A+ to F: the larger increase on Waveform's scale (REFERENCES.md § R3), as Waveform grades. One measured input read against a cited scale ([ADR-004](ARCHITECTURE_DECISIONS.md#adr-004-no-composite-health-sensors)) |
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

Tests run three ways: *Automatic tests*, the **Run speed test**
button, and automations that press it. Automatic tests are on by
default once a service is chosen and start at a random time from 1 to
5 am local (Core `timing.py`): weekly with no data budget, or as often
as the budget holds every test ([Data Use](#data-use)). HA's quality
rules bar a user-set interval (R16), so the user sets a budget and IHM
derives the spacing; an automation covers any other time or condition
(.github/README.md § Speed Testing). Overnight, a test is least likely to slow
a call or a game. IHM does not check whether the
line is busy: the FCC's test units do (R21), but they sit between modem
and router, and the HA host cannot see other devices' traffic.

Three settings bound the cost, counting every run, failed ones included:

| Setting | Default | Range | Why |
| --------- | --------- | ------- | ----- |
| Data limit per test | 0 (automatic) | 0, or 100 to 10000 MB | Automatic: sized for a whole test from the last result ([Data Use](#data-use)). Set by hand: each direction stops at half. The form refuses a limit larger than the budget |
| Daily test limit | 4 | 1 to 40 | Any 24 hours. 4 is M-Lab's limit for automated clients; 40 its limit for interactive users (R9) |
| Data budget per 30 days | 0 (none) | 0 to 10000 GB | A test starts only if its data limit fits what speed tests have left of it in the last 30 days, so it is never exceeded. It also sets how often automatic tests run. SamKnows aims for under 10% of a monthly cap on slower plans (R22); IHM's advice is a small share |

With M-Lab, IHM also follows its rules for automated clients (R9). A
run with no person behind it (an automatic test, an automation or a
script) counts toward at most 4 a day, whatever the daily test limit
says. An automatic test already starts at a random time; one an
automation starts waits a random time of up to an hour, so homes
running the same automation do not test at the same moment; the press returns at once and the sensors update
when the test finishes. M-Lab asks for randomized times without naming
a window; one hour is IHM's choice. A person's press runs at once.

The Core command line (`--speed-test mlab`) follows the same rules. A run
whose standard input is not a terminal (cron, a script) is automated: it
counts toward the 4 and waits a random time of up to an hour. Any run past
40 in 24 hours, M-Lab's limit per client, is refused. Runs are recorded in
`mlab_runs.json` in the user's state directory (`$XDG_STATE_HOME`, default
`~/.local/state`, or `%LOCALAPPDATA%` on Windows, under
`internet-health-monitor`).

## Data Use

The rules in Core `data_plan.py`; .github/README.md § How Much Data Speed Tests
Use shows them for typical lines. A whole test beats a short one, so
IHM sizes each test to finish and spaces tests to fit the budget.

- **A full test** loads each direction for `SPEED_TEST_DIRECTION_S`
  (10 s), so it moves about that many seconds of each direction's
  speed: 1.25 MB per Mbit/s, about 1.3 GB on a 1000/40 line. Each
  result reports the exact amount (Data used).
- **Automatic data limit** (setting 0): each direction gets 10 s at the
  last test's speed, times `SPEED_TEST_AUTO_LIMIT_MARGIN` (1.25, IHM's
  choice, so a line up to a quarter faster still gets a whole test), up
  to the next 10 MB, from 50 to 5000 MB. Each direction stops at its
  own limit, so a slow upload does not cost a fast download its share.
  With no last result, the first test uses the default 500 MB, split
  evenly. A limit set by hand is split evenly.
- **Within the budget:** an automatic limit larger than the whole
  budget is cut to it, keeping the smaller direction whole where it can.
  The form refuses a hand-set limit larger than the budget.
- **Spacing:** with no budget, automatic tests run every
  `SPEED_TEST_AUTO_EVERY_DAYS_NO_BUDGET` (7) days. With one, the budget
  holds k tests at their limit; tests are spaced every
  ⌈(30 days + 5 h) ÷ k⌉ days, so no 30 days hold more than k even when
  each starts anywhere in its 4-hour window and a clock change moves it
  an hour. The budget therefore never refuses an automatic test. The
  next test is that many nights after the last automatic one; a test a
  limit refuses is tried the next night.
- **The working is shown:** the setup screen gives the last test's
  speeds, the limit per test, the days between automatic tests and the
  most they can use in any 30 days; each download and upload reading
  carries `ended_by` and `duration_s`.

## Backends

### Cloudflare

- **Choose it if** you want per-direction loaded latency from a large
  network, without your result being published.
- **Privacy:** Cloudflare says it truncates the address it receives to
  /24 (IPv4) or /48 (IPv6). The anonymized measurements it shares with
  partners come from its own speed test page; IHM does not post to
  Cloudflare's results endpoint (R5).
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
entry in `speed_test_runner._backends` and its name in `speed_test.BACKEND_NAMES`, tests against an in-process fake of the
provider, and a row in each table here and in
[ARCHITECTURE.md § Data Leaving the Host](ARCHITECTURE.md#data-leaving-the-host).
HTTP providers reuse the shared engine by describing their URLs.
