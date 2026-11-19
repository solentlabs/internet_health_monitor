"""DNS latency probe: one UDP query to a chosen server, timed in-process.

Message format per RFC 1035 § 4.1 (docs/REFERENCES.md § R14). The name is
random, so no cache can answer and the server resolves it each time; the
expected answer is NXDOMAIN. Standard library only, so it behaves the same
on every OS.
"""

from __future__ import annotations

import asyncio
import ipaddress
import secrets
import socket
import struct
import time
from typing import override

DNS_PORT = 53
RCODE_NOERROR = 0
RCODE_NXDOMAIN = 3
PROBE_DOMAIN = "cloudflare.com"
_FLAGS_RECURSION_DESIRED = 0x0100
_FLAG_QR = 0x8000
QTYPE_A = 1
QTYPE_TXT = 16
_QCLASS_IN = 1
_HEADER = struct.Struct("!HHHHHH")


def probe_name() -> str:
    """Return a random name under PROBE_DOMAIN that no cache will hold.

    The `_ihm-` prefix lets network admins see where the queries come from.
    """
    return f"_ihm-{secrets.token_hex(4)}.{PROBE_DOMAIN}"


def build_query(query_id: int, name: str, qtype: int = QTYPE_A) -> bytes:
    """Return a recursive query for name, class IN (RFC 1035 § 4.1.1-4.1.2)."""
    header = _HEADER.pack(query_id, _FLAGS_RECURSION_DESIRED, 1, 0, 0, 0)
    labels = b"".join(bytes([len(label)]) + label.encode("ascii") for label in name.split("."))
    return header + labels + b"\x00" + struct.pack("!HH", qtype, _QCLASS_IN)


def parse_rcode(data: bytes, query_id: int) -> int | None:
    """Return the response code if data is a reply to query_id, else None."""
    if len(data) < _HEADER.size:
        return None
    reply_id, flags, *_ = _HEADER.unpack_from(data)
    if reply_id != query_id or not flags & _FLAG_QR:
        return None
    rcode: int = flags & 0x000F
    return rcode


def _skip_name(data: bytes, offset: int) -> int:
    """Return the offset just past a (possibly compressed) name (RFC 1035 § 4.1.4)."""
    while offset < len(data):
        length = data[offset]
        if length & 0xC0 == 0xC0:  # pointer: two bytes, ends the name
            return offset + 2
        offset += 1 + length
        if length == 0:
            return offset
    raise ValueError("name runs past end of message")


def parse_txt_answers(data: bytes) -> list[str]:
    """Return the TXT strings in a reply's answer section (RFC 1035 § 3.3.14, § 4.1.3)."""
    _, _, qdcount, ancount, _, _ = _HEADER.unpack_from(data)
    offset = _HEADER.size
    for _ in range(qdcount):
        offset = _skip_name(data, offset) + 4  # QTYPE, QCLASS
    answers: list[str] = []
    for _ in range(ancount):
        offset = _skip_name(data, offset)
        rtype, _, _, rdlength = struct.unpack_from("!HHIH", data, offset)
        offset += 10
        rdata = data[offset : offset + rdlength]
        offset += rdlength
        if rtype != QTYPE_TXT:
            continue
        parts, pos = [], 0
        while pos < len(rdata):
            length = rdata[pos]
            parts.append(rdata[pos + 1 : pos + 1 + length].decode("utf-8", errors="replace"))
            pos += 1 + length
        answers.append("".join(parts))
    return answers


class _Exchange(asyncio.DatagramProtocol):
    """Sends one query and resolves with (reply bytes, receive time) on the matching reply."""

    def __init__(self, query: bytes, query_id: int, done: asyncio.Future[tuple[bytes, float]]) -> None:
        self._query = query
        self._query_id = query_id
        self._done = done
        self.sent_at = 0.0

    @override
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.sent_at = time.perf_counter()
        transport.sendto(self._query)  # type: ignore[attr-defined]

    @override
    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if parse_rcode(data, self._query_id) is not None and not self._done.done():
            self._done.set_result((data, time.perf_counter()))

    @override
    def error_received(self, exc: Exception) -> None:
        if not self._done.done():
            self._done.set_exception(exc)


async def _exchange(server: str, name: str, qtype: int, timeout_s: float, port: int) -> tuple[int, bytes, float] | None:
    """Send one query; return (rcode, reply, elapsed ms), or None on timeout or error."""
    loop = asyncio.get_running_loop()
    query_id = secrets.randbelow(0x10000)
    done: asyncio.Future[tuple[bytes, float]] = loop.create_future()
    family = socket.AF_INET6 if ipaddress.ip_address(server).version == 6 else socket.AF_INET
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: _Exchange(build_query(query_id, name, qtype), query_id, done),
        remote_addr=(server, port),
        family=family,
    )
    try:
        data, received_at = await asyncio.wait_for(done, timeout_s)
    except (TimeoutError, OSError):
        return None
    finally:
        transport.close()
    rcode = parse_rcode(data, query_id)
    if rcode is None:
        return None
    return rcode, data, (received_at - protocol.sent_at) * 1000


async def query_time_ms(server: str, timeout_s: float, port: int = DNS_PORT) -> float | None:
    """Time one resolution at server; None if it fails, errors or times out.

    NOERROR and NXDOMAIN both mean the server finished resolving the name.
    """
    result = await _exchange(server, probe_name(), QTYPE_A, timeout_s, port)
    if result is None or result[0] not in (RCODE_NOERROR, RCODE_NXDOMAIN):
        return None
    return result[2]


async def query_txt(server: str, name: str, timeout_s: float, port: int = DNS_PORT) -> list[str] | None:
    """Return the TXT answers for name ([] if none), or None if the query failed."""
    result = await _exchange(server, name, QTYPE_TXT, timeout_s, port)
    if result is None or result[0] not in (RCODE_NOERROR, RCODE_NXDOMAIN):
        return None
    try:
        return parse_txt_answers(result[1]) if result[0] == RCODE_NOERROR else []
    except (ValueError, struct.error):
        return None
