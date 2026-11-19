# Speed Test Backends

Which service runs your speed test, and what each choice means for you.
IHM lets you pick one
([ARCHITECTURE_DECISIONS.md § ADR-003](ARCHITECTURE_DECISIONS.md#adr-003-speed-testing-with-user-selected-backends-roadmap-phase-3)).
Sources and evidence labels: [REFERENCES.md § R9](REFERENCES.md#r9-speed-test-backend-survey-adr-003).
Facts marked *(unverified)* still need checking.

Status: planning. No backend is built yet.

## At a Glance

| Backend | Status | Bufferbloat reading | Your results made public? | Limits |
|---------|--------|---------------------|---------------------------|--------|
| **Cloudflare** | Candidate | Yes, idle and loaded latency per direction | No: collected, anonymized | Modest default schedule |
| **M-Lab NDT7** | First to be built | Approximate: good for download, weak for upload *(unverified)* | **Yes**, including your IP address, permanently | About 4 tests a day; hard limit 40 |
| **Fast.com** | Candidate | *(unverified)* | No: Netflix shares only aggregates | Modest default schedule; undocumented API may change |
| **LibreSpeed** public servers | Candidate | No: idle ping and jitter only | No *(telemetry to librespeed.org on by default in its client)* | Modest default schedule; volunteer servers |
| Ookla, built in | Not offered: personal, non-commercial license, and IHM won't accept it for you | | | |
| Self-hosted server | Not offered: IHM never requires running a server | | | |

Candidates may use public endpoints under the conditions in
[ARCHITECTURE_DECISIONS.md § ADR-003](ARCHITECTURE_DECISIONS.md#adr-003-speed-testing-with-user-selected-backends-roadmap-phase-3).
Each is a separate module, so new providers can be added.

IHM is not affiliated with any of these providers.

## M-Lab NDT7

Measurement Lab is a non-profit research platform that explicitly
welcomes automated tests from apps like IHM.

- **Choose it if** you want the provider with a published welcome for
  automated tests and don't mind your results being public.
- **Privacy:** M-Lab publishes every result, including your public IP
  address, date and time, and keeps it indefinitely. IHM asks you to
  confirm this before the first test, as M-Lab requires.
- **Schedule:** M-Lab asks automated clients for no more than 4 tests a
  day at random times. IHM's schedule follows that; on-demand tests also
  count toward M-Lab's daily limit.
- **Bufferbloat:** NDT7 has no dedicated loaded-latency test. IHM reports
  the server's round-trip time during the download as loaded latency,
  labelled as such. Upload loaded latency may not be reliable.

## Always Available Without a Speed Test

IHM's passive bufferbloat signal needs no backend: first-ISP-hop latency
rising while gateway latency stays flat points to a queue past your
router
([ARCHITECTURE_DECISIONS.md § ADR-001](ARCHITECTURE_DECISIONS.md#adr-001-bufferbloat-is-measured-passively-in-ihm)).
It uses almost no data.
