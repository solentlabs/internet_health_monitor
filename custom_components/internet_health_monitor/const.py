"""Constants for Internet Health Monitor."""

from __future__ import annotations

# Defaults and limits come from Core (timing.py), so the integration and the CLI agree.
from solentlabs.internet_health_monitor_core.network_diagnostics import DEFAULT_DNS_SERVER
from solentlabs.internet_health_monitor_core.speed_test import BACKEND_NAMES
from solentlabs.internet_health_monitor_core.timing import DEFAULT_PING_COUNT, PING_COUNT_MAX, PING_COUNT_MIN

__all__ = ["DEFAULT_DNS_SERVER", "DEFAULT_PING_COUNT", "PING_COUNT_MAX", "PING_COUNT_MIN"]

DOMAIN = "internet_health_monitor"
NAME = "Internet Health Monitor"
# The device, and so the start of every entity name and id. Users rename it
# in HA instead of a prefix setting (ADR-010).
DEVICE_NAME = "Internet Health"
MANUFACTURER = "Solent Labs"
TROUBLESHOOTING_URL = "https://github.com/solentlabs/internet_health_monitor#troubleshooting"
VERSION = "0.1.0"  # must equal manifest.json "version" (tests/components/test_const.py)

# Option keys
CONF_ENABLE_GATEWAY_MONITORING = "enable_gateway_monitoring"
CONF_ENABLE_DNS_MONITORING = "enable_dns_monitoring"
CONF_LONG_TERM_STATISTICS = "long_term_statistics"  # state_class on measurement sensors (ADR-013)
CONF_USAGE_TOTALS = "usage_totals"  # the six usage total sensors (README.md § Usage Totals)
CONF_DNS_SERVER = "dns_server"
CONF_PING_COUNT = "ping_count"
CONF_HOP_OWNERSHIP = "hop_ownership"  # opt-in; sends hop IPs to Team Cymru (ADR-006)
CONF_SPEED_TEST_BACKEND = "speed_test_backend"  # opt-in; docs/SPEED_TEST_BACKENDS.md (ADR-003, ADR-006)
CONF_SPEED_TEST_DATA_LIMIT = "speed_test_data_limit_mb"  # 0: automatic, from the last result
CONF_SPEED_TEST_DAILY_LIMIT = "speed_test_daily_limit"
CONF_SPEED_TEST_AUTOMATIC = "speed_test_automatic"  # tests spaced to fit the budget (Core data_plan.py)
CONF_SPEED_TEST_BUDGET = "speed_test_budget_gb"  # data per 30 days; 0 means none
CONF_MLAB_CONSENT = "mlab_consent"  # M-Lab publishes results with the user's IP; asked before first use

SPEED_TEST_OFF = "none"
# Off first; keys are translation keys (selector.speed_test_backend).
SPEED_TEST_CHOICES: list[str] = [SPEED_TEST_OFF, *BACKEND_NAMES]

# DNS server choice -> the server Core times. Keys are translation keys
# (selector.dns_server; hassfest allows only [a-z0-9-_]), so no addresses.
DNS_SERVERS: dict[str, str] = {
    DEFAULT_DNS_SERVER: DEFAULT_DNS_SERVER,  # "auto": the host's own resolver
    "cloudflare": "1.1.1.1",
    "google": "8.8.8.8",
    "quad9": "9.9.9.9",
    "opendns": "208.67.222.222",
}
