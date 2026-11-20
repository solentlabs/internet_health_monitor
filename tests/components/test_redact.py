"""Tests for what the diagnostics download leaves out."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.components.diagnostics import REDACTED

from custom_components.internet_health_monitor.redact import redact_diagnostics, redact_text

# ┌──────────────────────────────────────────────┬──────────────────────────────────────────────┐
# │ text                                         │ why                                          │
# ├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
# │ public IPv4 (documentation range stands in)  │ redacted: places the user                    │
# │ public IPv6                                  │ redacted, as IPv4                            │
# │ address with a port, at a sentence's end     │ redacted, punctuation kept                   │
# │ RFC 1918, shared (CGNAT), loopback           │ kept: reaches no one outside home or ISP     │
# │ IPv6 link-local, unique local, loopback      │ kept, as IPv4                                │
# │ a resolver IHM offers or falls back to       │ kept: says nothing about the user            │
# │ clock times, versions, latencies             │ kept: not addresses                          │
# └──────────────────────────────────────────────┴──────────────────────────────────────────────┘
# fmt: off
TEXT_CASES: list[tuple[str, str]] = [
    ("Detected hop 3: 198.51.100.7",                 f"Detected hop 3: {REDACTED}"),
    ("Using system DNS server: 2001:db8::53",        f"Using system DNS server: {REDACTED}"),
    ("query to 203.0.113.9:53 failed at 203.0.113.9.", f"query to {REDACTED}:53 failed at {REDACTED}."),
    ("Gateway is now 192.168.1.1 (was 10.0.0.1)",     "Gateway is now 192.168.1.1 (was 10.0.0.1)"),
    ("hop 2: 100.64.0.1, 172.16.5.4, 127.0.0.1",      "hop 2: 100.64.0.1, 172.16.5.4, 127.0.0.1"),
    ("fe80::1 fd00::1 ::1",                           "fe80::1 fd00::1 ::1"),
    ("trace target 8.8.8.8, DNS 208.67.222.222",      "trace target 8.8.8.8, DNS 208.67.222.222"),
    ("at 12:30:45, version 0.1.0, 1.2 ms",            "at 12:30:45, version 0.1.0, 1.2 ms"),
]
# fmt: on


@pytest.mark.parametrize("text,expected", TEXT_CASES)
def test_redact_text(text: str, expected: str) -> None:
    """Public addresses go; private ranges, offered resolvers and non-addresses stay."""
    assert redact_text(text) == expected


def test_redact_diagnostics() -> None:
    """Hostnames go by key, at any depth; every string is redacted as text; other values are untouched."""
    data: dict[str, Any] = {
        "result": {
            "hops": [
                {"ip": "192.168.1.1", "hostname": None, "latency_ms": 1.2},
                {"ip": "198.51.100.1", "hostname": "isp-router.example.com", "asn": 64500},
            ],
        },
        "logs": [{"level": "INFO", "message": "Detected 2 hops to 8.8.8.8: 192.168.1.1, 198.51.100.1"}],
    }
    assert redact_diagnostics(data) == {
        "result": {
            "hops": [
                {"ip": "192.168.1.1", "hostname": None, "latency_ms": 1.2},
                {"ip": REDACTED, "hostname": REDACTED, "asn": 64500},
            ],
        },
        "logs": [{"level": "INFO", "message": f"Detected 2 hops to 8.8.8.8: 192.168.1.1, {REDACTED}"}],
    }
