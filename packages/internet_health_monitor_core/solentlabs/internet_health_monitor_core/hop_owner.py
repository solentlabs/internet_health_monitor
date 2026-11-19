"""Hop owner lookup: which network operator (ASN) announces a hop's address.

Opt-in (off by default): it sends hop addresses to Team Cymru's IP-to-ASN
service over DNS (docs/REFERENCES.md § R15, ADR-006). Only public IPv4 hops
are looked up; private and shared ISP addresses (10/8, 100.64/10, ...)
have no owner to find. Country is deliberately not used: the service
"should not be used for IP geolocation" (R15).
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass

from . import dns_probe

_LOGGER = logging.getLogger(__name__)

ORIGIN_ZONE = "origin.asn.cymru.com"
ASN_ZONE = "asn.cymru.com"


@dataclass(frozen=True)
class HopOwner:
    """The network that announces a hop's address."""

    asn: int
    name: str | None


def origin_query_name(ip: str) -> str | None:
    """Return the origin-ASN query name for a public IPv4 address, else None."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if address.version != 4 or not address.is_global:
        return None
    return ".".join(reversed(ip.split("."))) + "." + ORIGIN_ZONE


def parse_origin_asn(txt: str) -> int | None:
    """Return the first origin ASN from "ASN [ASN...] | prefix | cc | registry | date"."""
    first = txt.split("|", 1)[0].split()
    return int(first[0]) if first and first[0].isdigit() else None


def parse_as_name(txt: str) -> str | None:
    """Return the AS description from "ASN | cc | registry | date | name"."""
    fields = [f.strip() for f in txt.split("|")]
    return fields[4] or None if len(fields) >= 5 else None


async def lookup_owner(ip: str, server: str, timeout_s: float) -> HopOwner | None:
    """Return who announces ip, asked through the given DNS server; None if unknown."""
    name = origin_query_name(ip)
    if name is None:
        return None
    origin = await dns_probe.query_txt(server, name, timeout_s)
    asn = parse_origin_asn(origin[0]) if origin else None
    if asn is None:
        _LOGGER.debug("No owner found for %s", ip)
        return None
    described = await dns_probe.query_txt(server, f"AS{asn}.{ASN_ZONE}", timeout_s)
    return HopOwner(asn=asn, name=parse_as_name(described[0]) if described else None)
