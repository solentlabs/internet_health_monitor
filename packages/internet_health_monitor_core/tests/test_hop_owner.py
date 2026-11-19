"""Tests for the opt-in hop owner (ASN) lookup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from solentlabs.internet_health_monitor_core import hop_owner
from solentlabs.internet_health_monitor_core.hop_owner import (
    HopOwner,
    lookup_owner,
    origin_query_name,
    parse_as_name,
    parse_origin_asn,
)

# Hop address -> query name; addresses with no public owner are not looked up
# fmt: off
QUERY_NAME_CASES = [
    ("public",          "8.8.8.8",          "8.8.8.8.origin.asn.cymru.com"),
    ("octets reversed", "8.8.4.4",          "4.4.8.8.origin.asn.cymru.com"),
    ("private",         "10.0.0.1",         None),
    ("shared ISP (CGNAT)", "100.64.0.1",    None),
    ("documentation",   "203.0.113.1",      None),
    ("IPv6",            "2001:4860::8888",  None),
    ("not an address",  "router.lan",       None),
]

# Team Cymru TXT answers (format per R15)
ORIGIN_CASES = [
    ("single",    "15169 | 8.8.8.0/24 | US | arin | 1992-12-01", 15169),
    ("multi-origin takes first", "7018 3356 | 192.0.2.0/24 | US | arin | 2000-01-01", 7018),
    ("garbage",   "no answer here", None),
]
AS_NAME_CASES = [
    ("name",      "15169 | US | arin | 2000-03-30 | GOOGLE - Google LLC, US", "GOOGLE - Google LLC, US"),
    ("empty",     "15169 | US | arin | 2000-03-30 | ",                        None),
    ("short",     "15169 | US",                                               None),
]
# fmt: on


@pytest.mark.parametrize(("description", "ip", "expected"), QUERY_NAME_CASES, ids=[c[0] for c in QUERY_NAME_CASES])
def test_origin_query_name(description: str, ip: str, expected: str | None) -> None:
    """Only public IPv4 hops are sent; the octets go in reverse order."""
    assert origin_query_name(ip) == expected


@pytest.mark.parametrize(("description", "txt", "expected"), ORIGIN_CASES, ids=[c[0] for c in ORIGIN_CASES])
def test_parse_origin_asn(description: str, txt: str, expected: int | None) -> None:
    """The ASN is the first field's first number."""
    assert parse_origin_asn(txt) == expected


@pytest.mark.parametrize(("description", "txt", "expected"), AS_NAME_CASES, ids=[c[0] for c in AS_NAME_CASES])
def test_parse_as_name(description: str, txt: str, expected: str | None) -> None:
    """The operator name is the fifth field."""
    assert parse_as_name(txt) == expected


# TXT results per query name -> owner
# fmt: off
LOOKUP_CASES = [
    ("owner and name",
     {"8.8.8.8.origin.asn.cymru.com": ["15169 | 8.8.8.0/24 | US | arin | 1992-12-01"],
      "AS15169.asn.cymru.com": ["15169 | US | arin | 2000-03-30 | GOOGLE - Google LLC, US"]},
     HopOwner(15169, "GOOGLE - Google LLC, US")),
    ("owner without name",
     {"8.8.8.8.origin.asn.cymru.com": ["15169 | 8.8.8.0/24 | US | arin | 1992-12-01"],
      "AS15169.asn.cymru.com": []},
     HopOwner(15169, None)),
    ("not announced", {"8.8.8.8.origin.asn.cymru.com": []}, None),
    ("query failed",  {"8.8.8.8.origin.asn.cymru.com": None}, None),
]
# fmt: on


@pytest.mark.parametrize(("description", "answers", "expected"), LOOKUP_CASES, ids=[c[0] for c in LOOKUP_CASES])
async def test_lookup_owner(description: str, answers: dict, expected: HopOwner | None) -> None:
    """Owner is the origin ASN plus its operator name, asked through the given server."""

    async def fake_txt(server: str, name: str, timeout_s: float) -> list[str] | None:
        assert server == "192.168.1.1"
        return answers[name]

    with patch.object(hop_owner.dns_probe, "query_txt", side_effect=fake_txt):
        assert await lookup_owner("8.8.8.8", "192.168.1.1", 2) == expected


async def test_private_hop_sends_nothing() -> None:
    """A private hop is never queried."""
    with patch.object(hop_owner.dns_probe, "query_txt", AsyncMock()) as query:
        assert await lookup_owner("10.0.0.1", "192.168.1.1", 2) is None
    query.assert_not_awaited()
