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

DNS_PORT = 53
RCODE_NOERROR = 0
RCODE_NXDOMAIN = 3
PROBE_DOMAIN = "cloudflare.com"
_FLAGS_RECURSION_DESIRED = 0x0100
_FLAG_QR = 0x8000
_QTYPE_A = 1
_QCLASS_IN = 1
_HEADER = struct.Struct("!HHHHHH")


def probe_name() -> str:
    """Return a random name under PROBE_DOMAIN that no cache will hold.

    The `_ihm-` prefix lets network admins see where the queries come from.
    """
    return f"_ihm-{secrets.token_hex(4)}.{PROBE_DOMAIN}"


def build_query(query_id: int, name: str) -> bytes:
    """Return a recursive query for name, type A, class IN (RFC 1035 § 4.1.1-4.1.2)."""
    header = _HEADER.pack(query_id, _FLAGS_RECURSION_DESIRED, 1, 0, 0, 0)
    labels = b"".join(bytes([len(label)]) + label.encode("ascii") for label in name.split("."))
    return header + labels + b"\x00" + struct.pack("!HH", _QTYPE_A, _QCLASS_IN)


def parse_rcode(data: bytes, query_id: int) -> int | None:
    """Return the response code if data is a reply to query_id, else None."""
    if len(data) < _HEADER.size:
        return None
    reply_id, flags, *_ = _HEADER.unpack_from(data)
    if reply_id != query_id or not flags & _FLAG_QR:
        return None
    rcode: int = flags & 0x000F
    return rcode


class _Exchange(asyncio.DatagramProtocol):
    """Sends one query and resolves with (rcode, receive time) on the matching reply."""

    def __init__(self, query: bytes, query_id: int, done: asyncio.Future[tuple[int, float]]) -> None:
        self._query = query
        self._query_id = query_id
        self._done = done
        self.sent_at = 0.0

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.sent_at = time.perf_counter()
        transport.sendto(self._query)  # type: ignore[attr-defined]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        rcode = parse_rcode(data, self._query_id)
        if rcode is not None and not self._done.done():
            self._done.set_result((rcode, time.perf_counter()))

    def error_received(self, exc: Exception) -> None:
        if not self._done.done():
            self._done.set_exception(exc)


async def query_time_ms(server: str, timeout_s: float, port: int = DNS_PORT) -> float | None:
    """Time one resolution at server; None if it fails, errors or times out.

    NOERROR and NXDOMAIN both mean the server finished resolving the name.
    """
    loop = asyncio.get_running_loop()
    query_id = secrets.randbelow(0x10000)
    done: asyncio.Future[tuple[int, float]] = loop.create_future()
    family = socket.AF_INET6 if ipaddress.ip_address(server).version == 6 else socket.AF_INET
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: _Exchange(build_query(query_id, probe_name()), query_id, done),
        remote_addr=(server, port),
        family=family,
    )
    try:
        rcode, received_at = await asyncio.wait_for(done, timeout_s)
    except (TimeoutError, OSError):
        return None
    finally:
        transport.close()
    if rcode not in (RCODE_NOERROR, RCODE_NXDOMAIN):
        return None
    return (received_at - protocol.sent_at) * 1000
