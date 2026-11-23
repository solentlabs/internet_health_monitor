"""ctypes bindings to the Windows IP Helper API (iphlpapi.dll). Windows only.

Calls return numbers and addresses, not text, so they work the same on any
Windows display language. Sources: docs/REFERENCES.md § R13. Exercised by
the Windows run (`make test-windows`), not by Linux unit tests.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import socket
import struct

# IP_STATUS codes (R13)
IP_SUCCESS = 0
IP_REQ_TIMED_OUT = 11010
IP_TTL_EXPIRED_TRANSIT = 11013

_NO_ERROR = 0
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_MAX_HOSTNAME_LEN = 128
_MAX_DOMAIN_NAME_LEN = 128
_MAX_SCOPE_ID_LEN = 256
_PAYLOAD = b"IHM-probe"


class _IpOptionInformation(ctypes.Structure):
    _fields_ = [
        ("Ttl", ctypes.c_ubyte),
        ("Tos", ctypes.c_ubyte),
        ("Flags", ctypes.c_ubyte),
        ("OptionsSize", ctypes.c_ubyte),
        ("OptionsData", ctypes.c_void_p),
    ]


class _IcmpEchoReply(ctypes.Structure):
    _fields_ = [
        ("Address", ctypes.c_uint32),
        ("Status", ctypes.c_ulong),
        ("RoundTripTime", ctypes.c_ulong),
        ("DataSize", ctypes.c_ushort),
        ("Reserved", ctypes.c_ushort),
        ("Data", ctypes.c_void_p),
        ("Options", _IpOptionInformation),
    ]


class _MibIpForwardRow(ctypes.Structure):
    _fields_ = [
        (name, ctypes.wintypes.DWORD)
        for name in (
            "dwForwardDest",
            "dwForwardMask",
            "dwForwardPolicy",
            "dwForwardNextHop",
            "dwForwardIfIndex",
            "dwForwardType",
            "dwForwardProto",
            "dwForwardAge",
            "dwForwardNextHopAS",
            "dwForwardMetric1",
            "dwForwardMetric2",
            "dwForwardMetric3",
            "dwForwardMetric4",
            "dwForwardMetric5",
        )
    ]


class _IpAddrString(ctypes.Structure):
    pass


_IpAddrString._fields_ = [
    ("Next", ctypes.POINTER(_IpAddrString)),
    ("IpAddress", ctypes.c_char * 16),
    ("IpMask", ctypes.c_char * 16),
    ("Context", ctypes.wintypes.DWORD),
]


class _FixedInfo(ctypes.Structure):
    _fields_ = [
        ("HostName", ctypes.c_char * (_MAX_HOSTNAME_LEN + 4)),
        ("DomainName", ctypes.c_char * (_MAX_DOMAIN_NAME_LEN + 4)),
        ("CurrentDnsServer", ctypes.POINTER(_IpAddrString)),
        ("DnsServerList", _IpAddrString),
        ("NodeType", ctypes.c_uint),
        ("ScopeId", ctypes.c_char * (_MAX_SCOPE_ID_LEN + 4)),
        ("EnableRouting", ctypes.c_uint),
        ("EnableProxy", ctypes.c_uint),
        ("EnableDns", ctypes.c_uint),
    ]


def _to_dword(ip: str) -> int:
    """IPv4 text to a DWORD in network byte order, as the API expects."""
    value: int = struct.unpack("<I", socket.inet_aton(ip))[0]
    return value


def _to_text(dword: int) -> str:
    """DWORD in network byte order to IPv4 text."""
    return socket.inet_ntoa(struct.pack("<I", dword))


class IpHelper:
    """Thin wrapper; each method is one blocking API call (run it in an executor)."""

    def __init__(self) -> None:
        """Load iphlpapi.dll."""
        self._dll = ctypes.WinDLL("iphlpapi.dll", use_last_error=True)  # type: ignore[attr-defined]
        self._dll.IcmpCreateFile.restype = ctypes.wintypes.HANDLE
        self._dll.IcmpCloseHandle.argtypes = [ctypes.wintypes.HANDLE]
        self._dll.IcmpSendEcho.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.wintypes.WORD,
            ctypes.POINTER(_IpOptionInformation),
            ctypes.c_void_p,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
        ]
        self._dll.IcmpSendEcho.restype = ctypes.wintypes.DWORD

    def echo(self, ip: str, ttl: int, timeout_ms: int) -> tuple[int, str | None, int | None]:
        """Send one echo request; return (IP_STATUS, replying address, round-trip ms)."""
        handle = self._dll.IcmpCreateFile()
        if handle in (None, _INVALID_HANDLE_VALUE):
            raise OSError(ctypes.get_last_error(), "IcmpCreateFile failed")  # type: ignore[attr-defined]
        try:
            options = _IpOptionInformation(Ttl=ttl)
            # Reply buffer: one reply + request data + 8 bytes for an ICMP error (R13)
            size = ctypes.sizeof(_IcmpEchoReply) + len(_PAYLOAD) + 8
            buffer = ctypes.create_string_buffer(size)
            count = self._dll.IcmpSendEcho(
                handle, _to_dword(ip), _PAYLOAD, len(_PAYLOAD), ctypes.byref(options), buffer, size, timeout_ms
            )
            reply = _IcmpEchoReply.from_buffer(buffer)
            if count == 0 and reply.Status == IP_SUCCESS:
                return IP_REQ_TIMED_OUT, None, None
            address = _to_text(reply.Address) if reply.Address else None
            return reply.Status, address, reply.RoundTripTime
        finally:
            self._dll.IcmpCloseHandle(handle)

    def next_hop(self, destination: str) -> str | None:
        """Return the next hop the routing table uses for destination, or None if on-link."""
        row = _MibIpForwardRow()
        if self._dll.GetBestRoute(_to_dword(destination), 0, ctypes.byref(row)) != _NO_ERROR:
            return None
        return _to_text(row.dwForwardNextHop) if row.dwForwardNextHop else None

    def dns_servers(self) -> list[str]:
        """Return the configured DNS servers, in order."""
        size = ctypes.wintypes.ULONG(0)
        self._dll.GetNetworkParams(None, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if self._dll.GetNetworkParams(buffer, ctypes.byref(size)) != _NO_ERROR:
            return []
        info = _FixedInfo.from_buffer(buffer)
        servers: list[str] = []
        entry: _IpAddrString | None = info.DnsServerList
        while entry is not None:
            text = entry.IpAddress.decode(errors="replace").strip("\x00 ")
            if text:
                servers.append(text)
            entry = entry.Next.contents if entry.Next else None
        return servers
