"""What the diagnostics download leaves out: anything that could place the user (ARCHITECTURE.md § Diagnostics)."""

from __future__ import annotations

import re
from ipaddress import ip_address, ip_network
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data

from solentlabs.internet_health_monitor_core.network_diagnostics import DEFAULT_TRACE_TARGET, FALLBACK_DNS_SERVER

from .const import DEFAULT_DNS_SERVER, DNS_SERVERS

# A hop's reverse DNS name often carries the subscriber's area or address.
REDACTED_KEYS = frozenset({"hostname"})
# Addresses that reach no one outside the home or the ISP (REFERENCES.md § R24).
KEPT_NETWORKS = tuple(
    ip_network(net)
    for net in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::/128",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)
# Public resolvers IHM offers or falls back to: shared by everyone, so they place no one.
KEPT_ADDRESSES = frozenset({*DNS_SERVERS.values(), FALLBACK_DNS_SERVER, DEFAULT_TRACE_TARGET} - {DEFAULT_DNS_SERVER})

_IPV4 = r"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?!\.?\d)"
_IPV6 = r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])"
_ADDRESS = re.compile(f"{_IPV4}|{_IPV6}")


def _kept(candidate: str) -> bool:
    """Whether a match stays: not an address at all, a non-public range, or an offered resolver."""
    try:
        address = ip_address(candidate)
    except ValueError:
        return True  # a clock time or other colon-separated text
    return candidate in KEPT_ADDRESSES or any(address in net for net in KEPT_NETWORKS)


def redact_text(text: str) -> str:
    """Replace each public address in *text* with HA's redaction marker."""
    return _ADDRESS.sub(lambda m: m[0] if _kept(m[0]) else REDACTED, text)


def _redact_strings(value: Any) -> Any:
    """Apply redact_text to every string, at any depth."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: _redact_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_strings(item) for item in value]
    return value


def redact_diagnostics(data: dict[str, Any]) -> dict[str, Any]:
    """Hostnames by key, then public addresses wherever they appear, logs included."""
    redacted: dict[str, Any] = _redact_strings(async_redact_data(data, REDACTED_KEYS))
    return redacted
