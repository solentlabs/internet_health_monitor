"""Constants for Internet Health Monitor."""

from __future__ import annotations

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

DEFAULT_DNS_SERVER = "auto"  # the host's own resolver
DEFAULT_PING_COUNT = 3

# DNS server choices; labels are in the translations (selector.dns_server)
DNS_SERVERS = ("auto", "1.1.1.1", "8.8.8.8", "9.9.9.9", "208.67.222.222")
