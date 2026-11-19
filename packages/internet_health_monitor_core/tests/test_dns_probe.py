"""Tests for the DNS probe: query bytes, reply parsing, and a timed UDP exchange."""

from __future__ import annotations

import asyncio
import struct

import pytest

from solentlabs.internet_health_monitor_core.dns_probe import (
    RCODE_NOERROR,
    RCODE_NXDOMAIN,
    build_query,
    parse_rcode,
    query_time_ms,
)


def _reply(query_id: int, rcode: int, qr: bool = True) -> bytes:
    """A reply header (RFC 1035 § 4.1.1) with no records."""
    flags = (0x8000 if qr else 0) | 0x0100 | 0x0080 | rcode
    return struct.pack("!HHHHHH", query_id, flags, 1, 0, 0, 0)


# Reply bytes -> RCODE for query id 0x1234; None means not a reply to this query
# fmt: off
RCODE_CASES = [
    ("nxdomain",         _reply(0x1234, 3),            RCODE_NXDOMAIN),
    ("noerror",          _reply(0x1234, 0),            RCODE_NOERROR),
    ("servfail",         _reply(0x1234, 2),            2),
    ("other query's id", _reply(0x9999, 3),            None),
    ("a query, not reply", _reply(0x1234, 0, qr=False), None),
    ("truncated header", b"\x12\x34\x81",              None),
]
# fmt: on


def test_build_query() -> None:
    """Header asks one recursive question; the name is length-prefixed labels; type A, class IN."""
    data = build_query(0x1234, "_ihm-ab12.example.com")
    assert data[:12] == struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    assert data[12:] == b"\x09_ihm-ab12\x07example\x03com\x00" + struct.pack("!HH", 1, 1)


@pytest.mark.parametrize(("description", "data", "expected"), RCODE_CASES, ids=[c[0] for c in RCODE_CASES])
def test_parse_rcode(description: str, data: bytes, expected: int | None) -> None:
    """Only a reply (QR set) carrying our query id counts."""
    assert parse_rcode(data, 0x1234) == expected


class _FakeDnsServer(asyncio.DatagramProtocol):
    """In-process DNS server on 127.0.0.1 answering with a fixed RCODE."""

    def __init__(self, rcode: int | None) -> None:
        self.rcode = rcode
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if self.rcode is not None and self.transport:
            self.transport.sendto(_reply(struct.unpack("!H", data[:2])[0], self.rcode), addr)


# Server behaviour -> measured? (NOERROR and NXDOMAIN both mean resolution finished)
# fmt: off
EXCHANGE_CASES = [
    ("nxdomain answered", RCODE_NXDOMAIN, True),
    ("noerror answered",  RCODE_NOERROR,  True),
    ("servfail",          2,              False),
    ("no answer",         None,           False),
]
# fmt: on


@pytest.mark.parametrize(("description", "rcode", "measured"), EXCHANGE_CASES, ids=[c[0] for c in EXCHANGE_CASES])
async def test_query_time_ms(description: str, rcode: int | None, measured: bool) -> None:
    """A finished resolution gives a time; failure or silence gives None."""
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(lambda: _FakeDnsServer(rcode), local_addr=("127.0.0.1", 0))
    port = transport.get_extra_info("sockname")[1]
    try:
        result = await query_time_ms("127.0.0.1", timeout_s=0.3, port=port)
    finally:
        transport.close()
    assert (result is not None) is measured
    if measured:
        assert result is not None and 0 <= result < 300
