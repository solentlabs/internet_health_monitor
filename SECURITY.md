# Security Policy

## Supported versions

Security fixes go into the latest release only; update to it to receive
them. See [Releases](https://github.com/solentlabs/internet_health_monitor/releases).

## Reporting a vulnerability

**Please do not report a vulnerability in a public issue or Discussion.**
Report it privately on GitHub instead: the repository's **Security** tab →
**Report a vulnerability**, or
[this link](https://github.com/solentlabs/internet_health_monitor/security/advisories/new).
Only the maintainer sees it.

Please include as much as you can:

- What kind of problem it is (for example command injection, data leaking
  to an outside service, or something left out of the diagnostics redaction)
- The affected file, or the version and setting where it shows
- Steps to reproduce, and a proof of concept if you have one
- What an attacker could do with it

## What to expect

IHM is maintained by one person ([SUPPORT.md](SUPPORT.md)). Security
reports are read before anything else. You will get an acknowledgement,
then updates as the fix progresses. The fix ships as a new release with a
GitHub security advisory, crediting you unless you prefer otherwise.
Please keep the details private until that release is out.

## How IHM is built

[docs/ARCHITECTURE.md § Security](docs/ARCHITECTURE.md#security) states
each guarantee, and a test holds each one. In short:

- **No shell.** Commands (`ip`, `ping`, `traceroute`) run as argument
  lists, and only text that parses as an IP address reaches them.
- **Nothing secret is held.** IHM stores no credentials and never reads
  your public IP address.
- **What leaves your network is listed.** Probes go to your gateway, the
  hops, your DNS server and the internet reference (Cloudflare's 1.1.1.1
  by default, or off); anything else is an outside service you turn on
  yourself ([§ Data Leaving the Host](docs/ARCHITECTURE.md#data-leaving-the-host)).
- **Speed test servers need TLS.** Addresses a provider hands back are
  used only over `https://` or `wss://`, with certificate checks.
- **The diagnostics download is redacted.** Hop hostnames and public IP
  addresses are removed ([§ Diagnostics](docs/ARCHITECTURE.md#diagnostics)).
- **Scanned.** GitHub CodeQL checks every push to `main`, every pull
  request, and the whole repository weekly.
