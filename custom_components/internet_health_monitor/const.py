"""Constants for Internet Health Monitor integration."""

from __future__ import annotations

DOMAIN = "internet_health_monitor"
NAME = "Internet Health Monitor"
MANUFACTURER = "Solent Labs"
VERSION = "0.3.0"

# Config keys
CONF_ENABLE_GATEWAY_MONITORING = "enable_gateway_monitoring"
CONF_ENABLE_DNS_MONITORING = "enable_dns_monitoring"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DNS_SERVER = "dns_server"
CONF_PING_COUNT = "ping_count"

# Defaults
DEFAULT_SCAN_INTERVAL = 60  # seconds
DEFAULT_DNS_SERVER = "auto"  # Auto-detect from system
DEFAULT_PING_COUNT = 3
DEFAULT_PING_TIMEOUT = 2  # seconds
DEFAULT_DNS_TIMEOUT = 5  # seconds

# Predefined DNS servers
DNS_SERVERS = {
    "auto": "Auto-detect",
    "1.1.1.1": "Cloudflare",
    "8.8.8.8": "Google",
    "9.9.9.9": "Quad9",
    "208.67.222.222": "OpenDNS",
}
