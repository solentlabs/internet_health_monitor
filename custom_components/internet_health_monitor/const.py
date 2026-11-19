"""Constants for Internet Health Monitor."""

from __future__ import annotations

# Defaults and limits come from Core (timing.py), so the integration and the CLI agree.
from solentlabs.internet_health_monitor_core.network_diagnostics import DEFAULT_DNS_SERVER
from solentlabs.internet_health_monitor_core.timing import DEFAULT_PING_COUNT, PING_COUNT_MAX, PING_COUNT_MIN

__all__ = ["DEFAULT_DNS_SERVER", "DEFAULT_PING_COUNT", "PING_COUNT_MAX", "PING_COUNT_MIN"]

DOMAIN = "internet_health_monitor"
NAME = "Internet Health Monitor"
MANUFACTURER = "Solent Labs"
TROUBLESHOOTING_URL = "https://github.com/solentlabs/internet-health-monitor#troubleshooting"
VERSION = "0.1.0"  # must equal manifest.json "version" (tests/components/test_const.py)

# Option keys
CONF_ENABLE_GATEWAY_MONITORING = "enable_gateway_monitoring"
CONF_ENABLE_DNS_MONITORING = "enable_dns_monitoring"
CONF_DNS_SERVER = "dns_server"
CONF_PING_COUNT = "ping_count"
CONF_HOP_OWNERSHIP = "hop_ownership"  # opt-in; sends hop IPs to Team Cymru (ADR-006)

# DNS server choice -> the server Core times. Keys are translation keys
# (selector.dns_server; hassfest allows only [a-z0-9-_]), so no addresses.
DNS_SERVERS: dict[str, str] = {
    DEFAULT_DNS_SERVER: DEFAULT_DNS_SERVER,  # "auto": the host's own resolver
    "cloudflare": "1.1.1.1",
    "google": "8.8.8.8",
    "quad9": "9.9.9.9",
    "opendns": "208.67.222.222",
}
