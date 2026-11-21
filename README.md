# Internet Health Monitor

[![GitHub Release](https://img.shields.io/github/v/release/solentlabs/internet_health_monitor?include_prereleases)](https://github.com/solentlabs/internet_health_monitor/releases)
[![HA analytics installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=HA%20analytics&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.internet_health_monitor.total)](https://analytics.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

See where your internet slows down, from Home Assistant. Internet Health Monitor measures latency, jitter and packet loss to your router and the next two routers past it, so a problem shows whether it starts at home, at your ISP or beyond. Works with any ISP.

## What you get

- **The path, hop by hop.** Latency, jitter and packet loss for your gateway, your ISP's first router and the one after it, every 60 seconds.
- **DNS latency.** One uncached lookup per poll at your DNS server, or one you pick.
- **Reachability.** Gateway reachable and Internet reachable, for automations.
- **Speed tests you control.** Off by default. Cloudflare, M-Lab or LibreSpeed, run on a button or automatically overnight, spaced to fit your data budget.
- **Bufferbloat.** Each speed test graded A+ to F on Waveform's scale.
- **A dashboard card.** Pick Internet Health in Add card and set it up in a form; no YAML.
- **Zero configuration.** Gateway, hops and DNS server are detected automatically.

## Dashboard

![Internet Health dashboard card](https://raw.githubusercontent.com/solentlabs/internet_health_monitor/main/images/dashboard-screenshot-dark.png)

[More on GitHub](https://github.com/solentlabs/internet_health_monitor#dashboard-card)

## Setup

Requires Home Assistant 2026.10 or later on Linux (HA OS, Container, Supervised or Core).

1. Internet Health Monitor is in beta: open **Settings → Marketplace**, add `https://github.com/solentlabs/internet_health_monitor` as a custom repository (type Integration), and install the latest beta ([beta steps](https://github.com/solentlabs/internet_health_monitor#testing-a-beta-release)). On Home Assistant before 2026.11, use HACS the same way.
2. Restart Home Assistant.
3. Settings → Devices & Services → Add Integration → "Internet Health Monitor". Every setting has a default; gateway, hops and DNS server are found on their own.

## Privacy and security

Pings and traceroutes go only to your router and your ISP's next two routers, and DNS lookups to your own DNS server. Nothing goes to an outside service unless you choose it: a public DNS server to time instead of yours, a speed test service (M-Lab publishes your IP address with every result, and asks you first), or hop ownership, which sends your ISP's router addresses, never your own, to Team Cymru. GitHub CodeQL scans every push to main, every pull request and weekly.

## Using the integration

- [Full documentation](https://github.com/solentlabs/internet_health_monitor#readme): every setting, sensor and attribute
- [Speed tests and data use](https://github.com/solentlabs/internet_health_monitor#speed-testing): the services compared, and how much data a test uses
- [Troubleshooting](https://github.com/solentlabs/internet_health_monitor#troubleshooting): missing hops, missing tools, reporting a problem
- [Changelog](https://github.com/solentlabs/internet_health_monitor/blob/main/CHANGELOG.md): what changed in each release

## Support

Bugs go to [GitHub Issues](https://github.com/solentlabs/internet_health_monitor/issues), with the diagnostics download; questions and ideas to [GitHub Discussions](https://github.com/solentlabs/internet_health_monitor/discussions).

## License

MIT. The project's names and logos are not covered by it; see [TRADEMARKS.md](https://github.com/solentlabs/internet_health_monitor/blob/main/TRADEMARKS.md).
