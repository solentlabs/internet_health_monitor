# Use Cases

Each use case names who, what they need, and how we know it works. Tests
trace back to a `UC-` id. Numbering is kept from the retired BufferBloat
design so references stay stable; gaps are use cases that only applied
to an active load test
([ARCHITECTURE_DECISIONS.md § ADR-001](ARCHITECTURE_DECISIONS.md#adr-001-bufferbloat-is-measured-passively-in-ihm)).

## Motivating Case

A household on a 100/10 Mbps cable plan with a 1.25 TB monthly cap and a
mesh Wi-Fi system with no SQM. A cloud-gaming session lags whenever
someone views a security camera's live video. The suspected cause is
upload bufferbloat: camera video saturates the 10 Mbps uplink, and the
modem's or router's queue adds latency to every other flow. This
assumes camera viewing is relayed through the vendor's cloud (uplink
traffic) rather than streamed on the LAN; unverified.

## UC-3: Confirm upload bloat is the cause

**Who:** The motivating household.
**Need:** Evidence that latency past the modem rises when the uplink is
busy.
**Done when:** First-ISP-hop latency and gateway latency are separate
entities, so a history graph shows the hop rising above its idle
baseline while the gateway stays flat, lined up against the camera's
streaming state.

Passive measurement cannot separate upload from download queueing on
its own; the correlation with a known upload source (the camera) does.

## UC-5: Don't wreck the line to measure it

**Who:** Everyone in the household.
**Need:** Monitoring must not add load or burn the data cap.
**Done when:** IHM sends only small probes (ping, DNS). Any faster
probe cadence added for bloat tracking states its data cost.

## UC-6: Verify a fix

**Who:** A user who changed something (enabled SQM on a new router,
moved the camera to a lower bitrate, changed plan).
**Need:** Before/after comparison on the same targets.
**Done when:** Hop sensors expose the target IP as an attribute and, with
the *Long-term statistics* option on (ADR-013), keep long-term
statistics, so before/after periods are comparable, or visibly not when
the target changed. Within 10 days, state history alone serves.

## UC-7: Tell a modem problem from a queueing problem

**Who:** A Cable Modem Monitor user.
**Need:** "Modem signal is fine, bloat is bad" (or the reverse) from one
dashboard.
**Done when:** IHM and CMM entities combine in an HA template or
automation with no code dependency between them
([ARCHITECTURE_DECISIONS.md § ADR-002](ARCHITECTURE_DECISIONS.md#adr-002-ihm-stays-a-standalone-integration)).
IHM's part is stable entity ids and ms units.

## UC-8: Tell LAN/Wi-Fi queueing from WAN queueing

**Who:** A user who wants to know whether the bloat is in the mesh
Wi-Fi rather than the WAN.
**Done when:** Gateway latency rising with the ISP hop rising by the
same amount points to the LAN; ISP hop rising alone points to the WAN.
Both readings come from the same poll.

## UC-9: Tell a problem on the line from one past it

**Who:** Any user whose connection feels slow.
**Need:** A reading past the ISP's first routers, from a target built to
answer, so a slowdown can be placed at home (hop 1), on the line (hop
2), or beyond it.
**Done when:** An internet reference, on by default, reports latency,
jitter and packet loss from the same poll as the hops; the user can
change its provider or turn it off
([ARCHITECTURE_DECISIONS.md § ADR-015](ARCHITECTURE_DECISIONS.md#adr-015-internet-reference-ping-on-by-default-to-cloudflare)).

## Out of Scope

- Fixing bloat (router configuration, SQM).
- Per-device attribution ("which device caused it").
