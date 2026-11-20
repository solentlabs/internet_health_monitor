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

- <https://datatracker.ietf.org/doc/draft-ietf-ippm-responsiveness/>
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

<https://www.waveform.com/tools/bufferbloat>. Never contacted by our code.

| Fact | Label |
| ------ | ------- |
| Thresholds on latency increase: A+ < 5 ms, A < 30, B < 60, C < 200, D < 400, F ≥ 400. | [V] via Wayback capture 2026-11-07 of Waveform's production JS: <https://web.archive.org/web/20261107122556id_/https://www.waveform.com/tools/bufferbloat/assets/entry_v2-CNNFEkiB.js> |
| Grade = worst of download and upload increase over idle. | [V] same source |
| "Anything worse than a B may affect video calls." | [V] |

**License:** proprietary site. **Cite only**, as a fact, with link.
Wayback-only so far; a live re-read is an Open Verification Item.

## R4. DSLReports speed test grading (historical)

Archived FAQ: <https://web.archive.org/web/20230802002937/https://www.dslreports.com/faq/17930>.
Site shut down [V].

- Same cutoffs as R3 [V].
- Basis is the **average** of download and upload increase, not
  worst-of [V].

**Cite only.** Wayback-only.

## R5. Cloudflare speed test

- <https://github.com/cloudflare/speedtest>, MIT [V].
- Endpoints, from `src/config/defaultConfig.ts` and
  `src/engines/BandwidthEngine/BandwidthEngine.ts`, read 2026-11-19 [V]:
  `https://speed.cloudflare.com/__down?bytes=N` (GET) and `__up` (POST);
  no required headers.
- Latency: `bytes=0` requests; "ping = ttfb - baseServerTime -
  serverTimeDelta", server time from the `server-timing` header
  (`cfRequestDuration;dur=`, else the sum of `cfSpeed*;dur=` entries);
  median (`latencyPercentile: 0.5`). Loaded latency: one such request
  every `loadedLatencyThrottle: 400` ms during each direction [V].
- Results: README, "measurement results are collected by Cloudflare on
  completion"; the library posts them to `__results` unless
  `logAimApiUrl` is `null` [V]. IHM never posts.
- A real `bytes=0` request on 2026-11-19 returned `server-timing:
  cfSpeedEdge;dur=4, cfSpeedWorker;dur=18`, the summed form IHM reads [V].
- speed.cloudflare.com's privacy text says Cloudflare truncates the IP
  address it receives to /24 (IPv4) or /48 (IPv6) [U: read through a
  summarizer].
- No terms specific to speed.cloudflare.com. Cloudflare Website and
  Online Services Terms (<https://www.cloudflare.com/website-terms/>,
  effective 2025-08-01), read with curl 2026-11-19 [V*]: they cover
  websites "that Cloudflare operates and that link to these Terms";
  § 7 bars use that "could damage, disable, overburden, disrupt or
  impair any Cloudflare servers or APIs", exceeding "limitations on the
  Websites or Online Services, including on any API calls", and use
  "that violates any Cloudflare documentation"; § 8 bars automated bots
  only "for developing, training, fine-tuning, or otherwise contributing
  to or improving a machine learning model or artificial intelligence
  (AI) system". No permission was sought or obtained.

## R6. crusader

<https://github.com/Zoxc/crusader>. Rust, MIT / Apache-2.0, v0.3.2
(2024-10-03) [V]. LAN client/server latency-under-load tool; latency
sampled every 5 ms over UDP [V]. Useful for a manual LAN vs WAN check
(UC-8) if an active test is ever revisited.

## R7. bufferbloat.net testing guidance

<https://www.bufferbloat.net/projects/bloat/wiki/Tests_for_Bufferbloat/>
(updated 2026-01-26) [V]

- Recommends web tests (Waveform, Cloudflare, LibreQoS), a "ping during
  a speed test" quick test, and Flent RRUL as the best test [V].
- Rule of thumb: "above 50 msec, or a grade lower than 'B'" is a
  problem [V].
- RRUL spec (<https://www.bufferbloat.net/projects/bloat/wiki/RRUL_Spec/>):
  measure unloaded and saturated; insufficient tester CPU invalidates a
  test [V].

**License:** site content CC BY-SA 4.0 [V]. **Cite only;** quoting
requires attribution and share-alike.

## R8. Prior art in Home Assistant

| Project | What it does | License | Label |
| --------- | -------------- | --------- | ------- |
| HA core | No bufferbloat or responsiveness integration. `speedtestdotnet` and `fastdotcom` report no loaded latency. | Apache-2.0 | [V] |
| **soulripper13/hass-speedtest-ookla** (HACS default) | Wraps Ookla's CLI. Loaded latency IQM per direction and a "Bufferbloat Grade": `max(dl_iqm, ul_iqm) - idle`, A+ ≤ 5, A ≤ 30, B ≤ 60, C ≤ 120, D ≤ 300, E ≤ 600, F > 600. Matches R3 only up to B. | MIT | [V*] <https://raw.githubusercontent.com/soulripper13/hass-speedtest-ookla/main/custom_components/ookla_speedtest/__init__.py> |
| Ookla CLI (its dependency) | EULA: "personal, non-commercial use on a single personal computer". | Proprietary | [V] |
| DigitallyRefined/ha-cloudflare-speed-test | Idle latency and jitter, no loaded latency. | MIT | [V] README, [U] code |
| lynxthecat/cake-autorate `mqtt-publisher.sh` | OpenWrt only. MQTT discovery of shaper rates and delay deltas. No grade. | GPL-2.0 | [V] |

**How these integrations reach their providers** (read 2026-11-18):

- hass-speedtest-ookla downloads the Ookla CLI itself and runs
  `[SPEEDTEST_BIN_PATH, "--accept-license", "--accept-gdpr", "--format=json"]`;
  its README says nothing on Ookla's terms [V]
  <https://raw.githubusercontent.com/soulripper13/hass-speedtest-ookla/main/custom_components/ookla_speedtest/__init__.py>
- ha-cloudflare-speed-test uses cloudflarepycli against
  speed.cloudflare.com, "every hour" by default, "not affiliated or
  associated with Cloudflare"; no permission statement [V]
  <https://github.com/DigitallyRefined/ha-cloudflare-speed-test>

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

- <https://www.measurementlab.net/develop/>: "M-Lab welcomes automated and
  repeated testing." Integrations should test "no more than 4 times per
  day" at Poisson-randomized times; hard limit "40 tests per client per
  day" [V].
- AUP <https://www.measurementlab.net/aup/>: "measurements must be actively
  initiated based on informed consent", with a link to M-Lab's privacy
  policy; "Integration developers with commercial applications need to
  contribute to the platform" [V].
- Privacy <https://www.measurementlab.net/privacy/>: results, including
  IP addresses, are "published publicly" and "retained indefinitely" [V].
- Client: ndt7-client-go, Apache-2.0, v0.10.1 (2026-01-26). It must
  identify itself by client name; access tokens come from Locate API v2
  [V]. No Python client on PyPI [V].
- Latency: no dedicated loaded-latency test. The server reports TCPInfo
  `RTT` and `MinRTT` (<https://github.com/m-lab/ndt-server/blob/main/spec/ndt7-protocol.md>) [V].
  Using them as idle and download loaded latency, and their upload
  reliability, is [U].

- Locate API v2 (<https://www.measurementlab.net/develop/locate-v2/>) and
  `api/v2/api.go` (github.com/m-lab/locate), read 2026-11-19 [V]:
  `https://locate.measurementlab.net/v2/nearest/ndt/ndt7` returns
  `results[]` with `machine`, `location` and `urls`, e.g. key
  `wss:///ndt/v7/download` with an `access_token`, and
  `wss:///ndt/v7/upload` (confirmed by a real test from the developer's
  connection, 2026-11-19) [V].
  `client_name` and `client_version` are recommended query parameters
  (ndt7-js README) [V].
- Protocol (`spec/ndt7-protocol.md`, github.com/m-lab/ndt-server,
  Apache-2.0), read 2026-11-19 [V]: subprotocol
  `net.measurementlab.ndt.v7`; "The client SHOULD also include a
  meaningful, non-generic User-Agent string"; binary messages "SHOULD
  initially be sending binary messages containing 1 << 13 bytes",
  doubling "when it is smaller than 1/16 of the queued bytes"; "The
  expected duration of a test is *up to* ten seconds"; a client "MAY
  close" after thirteen; `MinRTT` and `RTT` are "measured in
  microseconds"; `AppInfo.NumBytes` counts application bytes; Locate
  `204` is "the no-capacity signal".
- AUP (<https://www.measurementlab.net/aup/>), read with curl 2026-11-19
  [V*]: "Interactive users must not run more than 40 tests per day.
  Automated software or hardware clients should not run more than 4
  tests per day, and test times should be randomized"; "Automated and
  repeated testing requires user consent and care in implementation".
- Developer guide (<https://www.measurementlab.net/develop/>), read with
  curl 2026-11-19 [V*]: "Clients are required to provide informed consent
  about collection of personal information"; "Clients that hit this rate
  limit will be provided a 204 No Content response".
- Privacy (<https://www.measurementlab.net/privacy/>), read with curl
  2026-11-19 [V*]: "All experiment data is retained indefinitely and
  published publicly".

**M-Lab MSAK** (<https://github.com/m-lab/msak>): Apache-2.0, adds a UDP
`latency1` test [V]. Whether third-party use is permitted and whether
latency1 runs under load are [U].

**No permission basis found:** LibreSpeed public servers (no terms;
client LGPL-3.0; no loaded latency) [V]; Fast.com (undocumented API) [V];
Cloudflare (R5); Ookla (R8); nPerf, Apple (not assessed) [U].

**HA prior art:** no ndt7 or LibreSpeed integration found [V search].

## R10. Ping round-trip time

- **RFC 2681**, *A Round-trip Delay Metric for IPPM*
  (<https://www.rfc-editor.org/rfc/rfc2681.txt>). Round-trip delay is from
  when "Src sent the first bit" to when "Src received the last bit" of
  the reply, in wire-time. "ping" qualifies "with a Type-P of ICMP echo
  request/reply", but "the uncertainties associated with a typical ping
  program must be analyzed" [V].
- **iputils `ping(8)`** (<https://man7.org/linux/man-pages/man8/ping.8.html>):
  "Round-trip times and packet loss statistics are computed", from a
  timestamp carried in the packet payload; "Normally ping prints network
  round trip time" [V].
- **HA core `ping` integration**
  (<https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/ping/helpers.py>):
  uses icmplib's `min_rtt`/`avg_rtt`/`max_rtt`, or parses the
  min/avg/max(/mdev) summary of the `ping` binary, with a separate
  pattern for BusyBox output [V].

## R11. HA options flow `config_entry`

HA developer blog, 2024-11-12
(<https://contributors.home-assistant.io/blog/2024/11/12/options-flow/>):
`self.config_entry` is now a helper property HA provides on `OptionsFlow`;
setting it explicitly logs a warning and is allowed "until Home
Assistant Core 2025.12" [V]. HA 2026.9.3 raises `AttributeError:
property 'config_entry' ... has no setter` [V, local test log]. Exact
release that added the property [U].

## R12. Documentation addresses and names

RFC 5737 (<https://www.rfc-editor.org/rfc/rfc5737>): 192.0.2.0/24,
198.51.100.0/24 and 203.0.113.0/24 are reserved for documentation [V].
RFC 2606 (<https://www.rfc-editor.org/rfc/rfc2606>): `example.com`,
`example.net` and `example.org` are reserved for examples [V]. Used for
test fixtures (`CLAUDE.md § Code`).

## R13. Windows IP Helper API

Microsoft Learn, checked 2026-11-19:

- `IcmpSendEcho`
  (<https://learn.microsoft.com/en-us/windows/win32/api/icmpapi/nf-icmpapi-icmpsendecho>):
  exported from Iphlpapi.dll; "a synchronous function"; the reply buffer
  must hold one `ICMP_ECHO_REPLY` "plus RequestSize bytes of data" and "8
  more bytes" [V].
- `ICMP_ECHO_REPLY`
  (<https://learn.microsoft.com/en-us/windows/win32/api/ipexport/ns-ipexport-icmp_echo_reply>):
  `RoundTripTime` is a ULONG, "The round trip time, in milliseconds", so
  Windows readings are whole milliseconds [V]. Status codes: IP_SUCCESS 0,
  IP_REQ_TIMED_OUT 11010, IP_TTL_EXPIRED_TRANSIT 11013 [V].
- `IP_OPTION_INFORMATION`
  (<https://learn.microsoft.com/en-us/windows/win32/api/ipexport/ns-ipexport-ip_option_information>):
  `Ttl` is carried in the IPv4 header [V].
- `GetBestRoute` and `MIB_IPFORWARDROW`
  (<https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getbestroute>,
  <https://learn.microsoft.com/en-us/windows/win32/api/ipmib/ns-ipmib-mib_ipforwardrow>):
  `dwForwardNextHop` is the next system en route, in network byte order [V].
- `GetNetworkParams` and `FIXED_INFO`
  (<https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getnetworkparams>,
  <https://learn.microsoft.com/en-us/windows/win32/api/iptypes/ns-iptypes-fixed_info_w2ksp1>):
  `DnsServerList` is a linked list of `IP_ADDR_STRING` [V].

Not stated by Microsoft, confirmed by a local run on 64-bit Windows,
Python 3.12, no admin rights (2026-11-19): the native `ICMP_ECHO_REPLY`
layout parses correctly; on TTL expiry `Address` is the router that
answered; no elevation is needed [V, local run]. `MAX_HOSTNAME_LEN` and
`MAX_DOMAIN_NAME_LEN` of 128 come from the Windows SDK headers [U]; the
local run read the DNS server list correctly with them.

## R14. DNS message format

RFC 1035 (<https://www.rfc-editor.org/rfc/rfc1035>), read 2026-11-19:
§ 4.1.1 header (ID, QR bit marks a response, RD "Recursion Desired",
RCODE 0 no error and 3 "Name Error"), § 4.1.2 question (each label "a
length octet followed by that number of characters", QTYPE, QCLASS),
§ 3.2.2 TYPE A = 1, § 3.2.4 CLASS IN = 1, § 4.2.1 UDP usage [V]. Used by
`dns_probe.py`.

## R15. Team Cymru IP-to-ASN mapping

<https://www.team-cymru.com/ip-asn-mapping>, read 2026-11-19 [V]:

- DNS interface: "Reverse the octets and append the zone"
  (`origin.asn.cymru.com`); TXT answer "ASN | prefix | CC | registry |
  allocated"; "A prefix we do not hold returns NXDOMAIN". AS names from
  `AS<n>.asn.cymru.com`, answer "ASN | CC | registry | allocated | name".
- DNS is "Cacheable, low overhead, and the best fit for recurring
  lookups". Cost: "Free, forever." No formal terms of use are published.
- "this service should not be used for IP geolocation."
- Bulk guidance: "Keep each bulk run to a few thousand addresses"; IPs
  that "hammer" the whois server "are null routed". IHM sends at most
  six queries per hop detection.

Format confirmed by a live query for 8.8.8.8 (2026-11-19): ASN 15169,
"GOOGLE - Google LLC, US" [V, local run].

## R16. Polling intervals

HA's rule and guidance, read 2026-11-19 [V]:

- Quality scale `appropriate-polling`
  (<https://github.com/home-assistant/developers.home-assistant/blob/master/docs/core/integration-quality-scale/rules/appropriate-polling.md>):
  set "an appropriate polling interval that will serve the majority of
  users"; the interval "is not a field in the config flow"; users wanting
  more frequent updates "can define a custom polling interval"
  (<https://www.home-assistant.io/common-tasks/general/#defining-a-custom-polling-interval>).
- HA core's integration guidance
  (<https://github.com/home-assistant/core/blob/dev/.claude/skills/ha-integration-knowledge/SKILL.md>):
  "Polling intervals are NOT user-configurable. Never add scan_interval,
  update_interval, or polling frequency options to config flows or config
  entries."
- Counter-view: discussion #306
  (<https://github.com/orgs/home-assistant/discussions/306>) asks for
  configurable intervals and calls the automation route "not very user
  friendly".

Defaults of comparable tools, read from their source 2026-11-19 [V]:

| Tool | Interval | Probes per poll | Source |
| ------ | ---------- | ----------------- | -------- |
| HA Ping integration | 30 s | 5 pings | `homeassistant/components/ping/coordinator.py`, `const.py` (home-assistant/core, dev) |
| HA Speedtest.net integration | 60 min | one speed test | `speedtestdotnet/const.py` `DEFAULT_SCAN_INTERVAL = 60`, used as `timedelta(minutes=...)` in `coordinator.py` (HA 2026.10.4) |
| HA Fast.com integration | 1 h | one speed test | `fastdotcom/const.py` `DEFAULT_INTERVAL = 1`, used as `timedelta(hours=...)` in `coordinator.py` (HA 2026.10.4) |

Neither speed test integration offers an interval option; both mark
`appropriate-polling` done in their `quality_scale.yaml` (HA 2026.10.4) [V].
| Uptime Kuma | 60 s | one check | `src/pages/EditMonitor.vue` (louislam/uptime-kuma, master) |
| SmokePing | 300 s | 20 pings | `etc/config.dist.in` `step`, `pings` (oetiker/SmokePing, master) |

## R17. Probatio replaces voluptuous

HA developer blog, "Probatio is our validation engine", 2026-09-30
(<https://github.com/home-assistant/developers.home-assistant/blob/master/blog/2026-09-30-probatio-validation-engine.md>)
[V]: "Since Home Assistant Core 2026.9, schema validation runs on
Probatio instead of voluptuous"; `import voluptuous` still works through
an alias and "voluptuous is no longer installed at all"; "Core itself has
moved to importing Probatio directly"; reaching probatio's typed results
and translated errors "means importing `probatio` directly".

HA core `pyproject.toml` at release tags [V]: `voluptuous==0.15.2` up to
2026.7.0, `probatio==0.11.4` at 2026.9.0, `probatio==0.13.0` at 2026.10.0;
2026.9.0 and later require Python >=3.14.2. Local mypy runs (2026-11-19)
[V, local run]: HA 2026.9.4 still annotates flow `data_schema` as
voluptuous; 2026.10.4 annotates it as `probatio.schema.Schema`.

HA core strict typing settings: `mypy.ini`
(<https://github.com/home-assistant/core/blob/dev/mypy.ini>) [V].

## R18. Jitter

- RFC 3550 § 6.4.1 (<https://www.rfc-editor.org/rfc/rfc3550>), read
  2026-11-19 [V]: interarrival jitter "is defined to be the mean deviation
  (smoothed absolute value) of the difference D in packet spacing at the
  receiver compared to the sender for a pair of packets", updated as
  `J(i) = J(i-1) + (|D(i-1,i)| - J(i-1))/16`.
- RFC 5481 § 1 (<https://www.rfc-editor.org/rfc/rfc5481>) [V]: prefers
  "delay variation" because "jitter" has many meanings; the industry
  "predominantly implemented two specific formulations": IPDV, "where the
  reference is the previous packet in the stream", and PDV, against the
  minimum delay. RFC 3393 § 1.1 [V] likewise avoids the term.
- Cloudflare speed test, `src/Results/MeasurementCalculations.ts`
  (<https://github.com/cloudflare/speedtest>, MIT), read 2026-11-19 [V]:
  `getJitter` "Computes jitter (ms) as the mean absolute difference between
  consecutive latency samples. Returns `null` if fewer than 2 samples".

## R19. Fast.com

- No published API or terms of use: fast.com's page links only a
  privacy statement (<http://help.netflix.com/legal/fastprivacy>, updated
  2021-03-16), which covers "IP address" and "connection information
  such as speed and latency measurements" [V].
- Netflix Terms of Use (<https://help.netflix.com/legal/termsofuse>),
  read with curl 2026-11-19 [V*]: users may not "use any robot, spider,
  scraper or other automated means to access the Netflix service", and
  "Netflix service" means "the service provided by Netflix for
  discovering and accessing Netflix content. This includes all
  personalization, features and functionalities, recommendations and
  reviews, our websites, applications and user interfaces". On that
  reading the ban covers fast.com, so IHM does not offer it (ADR-003).
- Client method, from open-source clients, read 2026-11-19 [V]:
  maaslalani/fast `maas.go` finds the script with `app-[a-z0-9]+\.js`,
  the token with `token:"([^"]+)"`, then calls
  `https://api.fast.com/netflix/speedtest/v2` with `https`, `token` and
  `urlCount`; the reply has `targets[].url` and `location`. Latency is a
  GET with `Range: bytes=0-0`; upload is a POST to a target URL.
  Fast.com's own method is [U]: Netflix's engineering post could not be
  read.
- FAQ (<https://fast.com>, read 2026-11-19 [V]): "FAST.com performs a
  series of downloads from and uploads to Netflix servers" and reports
  two latencies, unloaded and loaded.
- `fastdotcom` 0.0.7 (PyPI, MIT, nkgilley/fast.com), the library HA
  core's Fast.com integration uses, read 2026-11-19 [V]: blocking
  `urllib`/`requests` with threads; returns `0` when the token cannot
  be fetched; sets no User-Agent; latency by ICMP via `icmplib`.

## R20. LibreSpeed

- Server list `https://librespeed.org/backend-servers/servers.php`
  (librespeed/speedtest-cli `speedtest/speedtest.go`), entries with
  `name`, `server`, `dlURL`, `ulURL`, `pingURL`, read 2026-11-19 [V].
- Backend (librespeed/speedtest, LGPL-3.0): `garbage.php?ckSize=N` sends
  N chunks of 1048576 bytes; `empty.php` takes uploads and pings; the
  official worker adds `r=` random values and uses
  `garbagePhp_chunkSize: 100` [V].
- Telemetry: `telemetry_level: 0, // 0=disabled` in the library;
  librespeed.org's own page has it enabled [V]. IHM sends none.
- No terms, acceptable-use policy or rate limit published for the public
  servers [V: none found on librespeed.org or either README].
- Upload body limits vary by server: on 2026-11-19 a listed server
  (Clouvider, New York) accepted 1 and 4 MB bodies and refused 8 MB with
  `413 Request Entity Too Large` [V]. nginx's default
  `client_max_body_size` is 1m [U: not read this pass]; IHM posts
  1,000,000-byte bodies to LibreSpeed servers.

## R21. FCC Measuring Broadband America

How a national program schedules home speed tests, read 2026-11-19 [V]:

- Technical Appendix to the Thirteenth MBA Report, fixed, 2023
  (<https://data.fcc.gov/download/measuring-broadband-america/2023/Technical-Appendix-fixed-2023.pdf>).
  Methods page: <https://www.fcc.gov/page/measuring-broadband-america-open-methodology>.
- Download and upload: "The test operates for a fixed duration of 10
  seconds", eight TCP connections (p. 28).
- Schedule (Table 8): download and upload to the off-net server once in
  each of 12am-6am, 6am-12pm, 12pm-6pm, 6pm-8pm, 8pm-10pm and 10pm-12am;
  estimated 75 MB a day at 10 Mbps down, 7.5 MB at 1 Mbps up.
- Busy line: tests wait while household traffic exceeds 200 kbps either
  way, retrying every 5 seconds "for up to six times before the test is
  abandoned".
- Caps: "Schedules were adjusted when required for specific tests to
  avoid triggering data usage limits applied by some ISPs."

## R22. SamKnows data use

- <https://samknows.zendesk.com/hc/en-gb/articles/115002327729-How-much-data-is-my-Whitebox-using>,
  read 2026-11-19 [V]: for a slower plan such as ADSL, "the testing
  should use less than 10% of your monthly cap (if you have one)"; "The
  faster your broadband connection, the more data the testing will
  use"; "the testing will not run when you are using the internet".
  SamKnows runs the FCC's test units (R21).

## R23. Home Assistant history and statistics

Read 2026-11-19 [V]:

- <https://data.home-assistant.io/docs/statistics/>: the states table
  keeps every state change "only for a limited time: 10 days by
  default"; long-term statistics "are compiled every hour ... They are
  never purged."
- Developer docs, sensor entity
  (<https://github.com/home-assistant/developers.home-assistant/blob/master/docs/core/entity/sensor.md>,
  § Long-term Statistics): a sensor is stored as long-term statistics
  "if the entity has `state_class` set".
- An integration can keep attributes out of the recorder
  (`_unrecorded_attributes`, `helpers/entity.py`, HA 2026.11) but not an
  entity's state; only the user's `recorder: exclude` does that.

## R24. Addresses that place no one

Read 2026-11-20 [V]:

- HA developer docs, integration diagnostics
  (<https://contributors.home-assistant.io/core/integrations/diagnostics/>):
  users post diagnostics in public issues, so "Location data, like
  coordinates and addresses" and "Personal information" stay out;
  `async_redact_data` replaces listed keys with `**REDACTED**`, and
  `None` passes through.
- RFC 1918 (<https://www.rfc-editor.org/rfc/rfc1918>) § 3: private
  blocks 10/8, 172.16/12, 192.168/16.
- RFC 6598 (<https://www.rfc-editor.org/rfc/rfc6598>): Shared Address
  Space 100.64.0.0/10, for carrier-grade NAT; packets using it "MUST
  NOT be forwarded across Service Provider boundaries."
- IANA special-purpose registries
  (<https://www.iana.org/assignments/iana-ipv4-special-registry/>,
  <https://www.iana.org/assignments/iana-ipv6-special-registry/>):
  127.0.0.0/8 loopback (RFC 1122) and 169.254.0.0/16 link local
  (RFC 3927), neither globally reachable; ::1/128 loopback and
  fe80::/10 link-local (RFC 4291), fc00::/7 unique local (RFC 4193).

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
