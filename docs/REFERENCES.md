# References

Annotated sources, with license and what we may reuse versus only cite.
Other docs cite entries here as `REFERENCES.md § R<n>`. Entries and
numbering carry over from the retired BufferBloat design
([ARCHITECTURE_DECISIONS.md § ADR-001](ARCHITECTURE_DECISIONS.md#adr-001-bufferbloat-is-measured-passively-in-ihm)).

**Evidence labels** (research pass of 2026-11-18, docs and source only,
no test traffic sent):

- **[V]** read at the cited URL.
- **[V*]** read at the cited URL and re-checked independently.
- **[U]** unverified or assumed. Must be verified before code depends on it.
- **[C]** our arithmetic from [V] inputs.

## R1. IETF draft-ietf-ippm-responsiveness-09

*Responsiveness under Working Conditions.* Relevant only if an active
test is ever revisited.

- https://datatracker.ietf.org/doc/draft-ietf-ippm-responsiveness/
- Latest revision -09, 2026-07-06, an Internet-Draft (bpm WG), not an
  RFC [V*].
- RPM = 60000 / RTT(ms), single-sided 95% trimmed mean; classes Poor
  < 300 RPM, Fair 300 to 1000, Good 1000 to 6000, Excellent > 6000 [V].
- Sequential mode (up and down separately) "should" be offered (§5.1.2) [V].

**License:** IETF Trust Legal Provisions (BCP 78); code components
Revised BSD. **Reuse:** method and formulas. **Cite only:** prose.

## R2. github.com/network-quality

Only if an active test is revisited.

- goserver: Go reference RPM server, MIT, last push 2025-10-21 [V].
  Usable as a self-hosted or LAN load server.
- goresponsiveness: Go client, GPL-2.0, dormant since 2024-01-30; its
  aggregates differ from R1 [V]. Cite only.
- Apple `networkQuality` servers: no published permission for
  third-party use [V that it is absent]. Treat as not permitted [U].

## R3. Waveform bufferbloat test (grading scale only)

https://www.waveform.com/tools/bufferbloat. Never contacted by our code.

| Fact | Label |
|------|-------|
| Thresholds on latency increase: A+ < 5 ms, A < 30, B < 60, C < 200, D < 400, F ≥ 400. | [V] via Wayback capture 2026-11-07 of Waveform's production JS: https://web.archive.org/web/20261107122556id_/https://www.waveform.com/tools/bufferbloat/assets/entry_v2-CNNFEkiB.js |
| Grade = worst of download and upload increase over idle. | [V] same source |
| "Anything worse than a B may affect video calls." | [V] |

**License:** proprietary site. **Cite only**, as a fact, with link.
Wayback-only so far; a live re-read is an Open Verification Item.

## R4. DSLReports speed test grading (historical)

Archived FAQ: https://web.archive.org/web/20230802002937/https://www.dslreports.com/faq/17930.
Site shut down [V].

- Same cutoffs as R3 [V].
- Basis is the **average** of download and upload increase, not
  worst-of [V].

**Cite only.** Wayback-only.

## R5. Cloudflare speed test

- https://github.com/cloudflare/speedtest, MIT [V].
- No terms found for speed.cloudflare.com. Cloudflare Website Terms
  (https://www.cloudflare.com/website-terms/) bar uses that "overburden,
  disrupt or impair" its servers [V]; whether that covers scheduled
  automated speed tests is [U]. No permission was sought or obtained.

## R6. crusader

https://github.com/Zoxc/crusader. Rust, MIT / Apache-2.0, v0.3.2
(2024-10-03) [V]. LAN client/server latency-under-load tool; latency
sampled every 5 ms over UDP [V]. Useful for a manual LAN vs WAN check
(UC-8) if an active test is ever revisited.

## R7. bufferbloat.net testing guidance

https://www.bufferbloat.net/projects/bloat/wiki/Tests_for_Bufferbloat/
(updated 2026-01-26) [V]

- Recommends web tests (Waveform, Cloudflare, LibreQoS), a "ping during
  a speed test" quick test, and Flent RRUL as the best test [V].
- Rule of thumb: "above 50 msec, or a grade lower than 'B'" is a
  problem [V].
- RRUL spec (https://www.bufferbloat.net/projects/bloat/wiki/RRUL_Spec/):
  measure unloaded and saturated; insufficient tester CPU invalidates a
  test [V].

**License:** site content CC BY-SA 4.0 [V]. **Cite only;** quoting
requires attribution and share-alike.

## R8. Prior art in Home Assistant

| Project | What it does | License | Label |
|---------|--------------|---------|-------|
| HA core | No bufferbloat or responsiveness integration. `speedtestdotnet` and `fastdotcom` report no loaded latency. | Apache-2.0 | [V] |
| **soulripper13/hass-speedtest-ookla** (HACS default) | Wraps Ookla's CLI. Loaded latency IQM per direction and a "Bufferbloat Grade": `max(dl_iqm, ul_iqm) - idle`, A+ ≤ 5, A ≤ 30, B ≤ 60, C ≤ 120, D ≤ 300, E ≤ 600, F > 600. Matches R3 only up to B. | MIT | [V*] https://raw.githubusercontent.com/soulripper13/hass-speedtest-ookla/main/custom_components/ookla_speedtest/__init__.py |
| Ookla CLI (its dependency) | EULA: "personal, non-commercial use on a single personal computer". | Proprietary | [V] |
| DigitallyRefined/ha-cloudflare-speed-test | Idle latency and jitter, no loaded latency. | MIT | [V] README, [U] code |
| lynxthecat/cake-autorate `mqtt-publisher.sh` | OpenWrt only. MQTT discovery of shaper rates and delay deltas. No grade. | GPL-2.0 | [V] |

**How these integrations reach their providers** (read 2026-11-18):
- hass-speedtest-ookla downloads the Ookla CLI itself and runs
  `[SPEEDTEST_BIN_PATH, "--accept-license", "--accept-gdpr", "--format=json"]`;
  its README says nothing on Ookla's terms [V]
  https://raw.githubusercontent.com/soulripper13/hass-speedtest-ookla/main/custom_components/ookla_speedtest/__init__.py
- ha-cloudflare-speed-test uses cloudflarepycli against
  speed.cloudflare.com, "every hour" by default, "not affiliated or
  associated with Cloudflare"; no permission statement [V]
  https://github.com/DigitallyRefined/ha-cloudflare-speed-test

**hass-speedtest-ookla v3.1.6 review notes** (commit dad6a77, read by
the BufferBloat session 2026-11-18, not re-checked here [U]):

- Latency-under-load sensors are disabled by default and have no
  `state_class`, so no long-term statistics.
- Manual mode plus a `start_time` silently starts daily scheduled tests
  after the first manual run (`__init__.py:271-272`).
- In interval mode a test runs 60 s after every HA restart.
- Non-timeout failures return `None`, so sensors keep stale values with
  no failure signal.
- No tests.

## R9. Speed test backend survey (ADR-003)

Research pass of 2026-11-18, docs only, no tests run. Only M-Lab
publishes a permission basis for automated third-party clients.

**M-Lab NDT7**
- https://www.measurementlab.net/develop/: "M-Lab welcomes automated and
  repeated testing." Integrations should test "no more than 4 times per
  day" at Poisson-randomised times; hard limit "40 tests per client per
  day" [V].
- AUP https://www.measurementlab.net/aup/: "measurements must be actively
  initiated based on informed consent", with a link to M-Lab's privacy
  policy; "Integration developers with commercial applications need to
  contribute to the platform" [V].
- Privacy https://www.measurementlab.net/privacy/: results, including
  IP addresses, are "published publicly" and "retained indefinitely" [V].
- Client: ndt7-client-go, Apache-2.0, v0.10.1 (2026-01-26). It must
  identify itself by client name; access tokens come from Locate API v2
  [V]. No Python client on PyPI [V].
- Latency: no dedicated loaded-latency test. The server reports TCPInfo
  `RTT` and `MinRTT` (https://github.com/m-lab/ndt-server/blob/main/spec/ndt7-protocol.md) [V].
  Using them as idle and download loaded latency, and their upload
  reliability, is [U].

**M-Lab MSAK** (https://github.com/m-lab/msak): Apache-2.0, adds a UDP
`latency1` test [V]. Whether third-party use is permitted and whether
latency1 runs under load are [U].

**No permission basis found:** LibreSpeed public servers (no terms;
client LGPL-3.0; no loaded latency) [V]; Fast.com (undocumented API) [V];
Cloudflare (R5); Ookla (R8); nPerf, Apple (not assessed) [U].

**HA prior art:** no ndt7 or LibreSpeed integration found [V search].

## R10. Ping round-trip time

- **RFC 2681**, *A Round-trip Delay Metric for IPPM*
  (https://www.rfc-editor.org/rfc/rfc2681.txt). Round-trip delay is from
  when "Src sent the first bit" to when "Src received the last bit" of
  the reply, in wire-time. "ping" qualifies "with a Type-P of ICMP echo
  request/reply", but "the uncertainties associated with a typical ping
  program must be analyzed" [V].
- **iputils `ping(8)`** (https://man7.org/linux/man-pages/man8/ping.8.html):
  "Round-trip times and packet loss statistics are computed", from a
  timestamp carried in the packet payload; "Normally ping prints network
  round trip time" [V].
- **HA core `ping` integration**
  (https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/ping/helpers.py):
  uses icmplib's `min_rtt`/`avg_rtt`/`max_rtt`, or parses the
  min/avg/max(/mdev) summary of the `ping` binary, with a separate
  pattern for BusyBox output [V].

## R11. HA options flow `config_entry`

HA developer blog, 2024-11-12
(https://contributors.home-assistant.io/blog/2024/11/12/options-flow/):
`self.config_entry` is now a helper property HA provides on `OptionsFlow`;
setting it explicitly logs a warning and is allowed "until Home
Assistant Core 2025.12" [V]. HA 2026.9.3 raises `AttributeError:
property 'config_entry' ... has no setter` [V, local test log]. Exact
release that added the property [U].

## Open Verification Items

1. Whether ISP routers deprioritize ICMP aimed at themselves, making a
   stable host just past the first hop the better bloat target
   (ADR-001). Needs a citation.
2. Probe cadence needed to catch bloat spikes; about 1 ping/s is an
   estimate, not a source (ADR-001).
3. Field check of the passive method on the motivating household
   (ADR-001).
4. Waveform and DSLReports figures read via Wayback only (R3, R4).
5. Backend survey follow-ups (R9): whether M-Lab's "contribute to the
   platform" clause applies to a free open-source integration; whether
   MSAK is open to third parties and measures latency under load;
   whether on-demand runs count toward the 4-per-day guidance; the
   exact Ookla EULA text (fetch blocked this pass).
6. Whether camera live view is relayed through the vendor cloud
   (USE_CASES.md § Motivating Case).
