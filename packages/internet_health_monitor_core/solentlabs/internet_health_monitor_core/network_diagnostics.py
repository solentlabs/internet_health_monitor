"""Network Diagnostics Module.

Provides lightweight network performance monitoring including:
- Gateway latency and reachability (local network)
- Multi-hop latency (network path visibility)
- Jitter (latency variance)
- Packet loss percentage
- DNS resolution timing (internet connectivity)

Network path visualization:
    [HA Host] --Gateway--> [Hop 1] --Hop 2--> [Hop 3] --...--> [DNS Server]
              (local)      (ISP)     (backbone)  (internet)
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from . import dns_probe
from .hop_owner import HopOwner, lookup_owner, origin_query_name
from .platforms import HostEnvironment, Platform, get_platform
from .platforms.base import is_ip
from .timing import (
    DEFAULT_DNS_TIMEOUT,
    DEFAULT_PING_COUNT,
    DEFAULT_PING_TIMEOUT,
    REVERSE_DNS_TIMEOUT_S,
    TRACE_RETRY_S,
)

_LOGGER = logging.getLogger(__name__)

# Targets. Intervals, timeouts and limits are in timing.py.
DEFAULT_DNS_SERVER = "auto"  # Auto-detect from system
FALLBACK_DNS_SERVER = "1.1.1.1"  # Fallback if detection fails
DEFAULT_TRACE_TARGET = "8.8.8.8"  # Default traceroute target
NUM_HOPS = 3  # Fixed: always trace 3 hops (gateway, ISP, backbone)

# Private IP ranges (RFC 1918 + link-local)
PRIVATE_IP_PREFIXES = (
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "192.168.",
    "169.254.",  # Link-local
    "127.",  # Loopback
)


def consecutive_jitter(rtts: list[float]) -> float | None:
    """Mean absolute difference between consecutive round-trip times; None under two.

    The consecutive-sample form of RFC 3550 interarrival jitter, as Cloudflare's
    speed test computes it (docs/REFERENCES.md § R18, ADR-009).
    """
    if len(rtts) < 2:
        return None
    return sum(abs(b - a) for a, b in zip(rtts, rtts[1:], strict=False)) / (len(rtts) - 1)


def format_ms(value: float | None) -> str:
    """Format a latency for logs; a missing measurement reads n/a, not 0.0ms."""
    return "n/a" if value is None else f"{value:.1f}ms"


def is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private range."""
    return ip.startswith(PRIVATE_IP_PREFIXES)


@dataclass
class ProbeCounts:
    """What this instance has sent since it was created: the network cost of monitoring."""

    pings: int = 0
    traceroutes: int = 0
    dns_queries: int = 0  # latency probes, reverse lookups and hop ownership queries

    def to_dict(self) -> dict[str, int]:
        """Plain data for JSON output and diagnostics."""
        return {"pings": self.pings, "traceroutes": self.traceroutes, "dns_queries": self.dns_queries}


@dataclass
class HopInfo:
    """Information about a single network hop."""

    hop_number: int
    ip: str | None
    latency_ms: float | None
    reachable: bool
    jitter_ms: float | None = None
    packet_loss_percent: float | None = None
    packets_sent: int = 0
    packets_received: int = 0
    hostname: str | None = None  # Reverse DNS name, if the hop has one
    # Who announces the hop's address; only with hop_ownership on (hop_owner.py)
    asn: int | None = None
    as_name: str | None = None

    # Typical location based on hop number
    @property
    def typical_location(self) -> str:
        """Return typical network location based on hop number."""
        if self.hop_number == 1:
            return "gateway"
        if self.hop_number == 2:
            return "isp"
        return "backbone"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "hop_number": self.hop_number,
            "ip": self.ip,
            "latency_ms": self.latency_ms,
            "jitter_ms": self.jitter_ms,
            "packet_loss_percent": self.packet_loss_percent,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "reachable": self.reachable,
            "hostname": self.hostname,
            "asn": self.asn,
            "as_name": self.as_name,
            "typical_location": self.typical_location,
        }
        return result


@dataclass
class NetworkDiagnosticsResult:
    """Result of network diagnostics check."""

    timestamp: float

    # Gateway metrics (local network - modem/router)
    gateway_ip: str | None
    gateway_reachable: bool
    gateway_latency_ms: float | None
    gateway_jitter_ms: float | None
    packet_loss_percent: float | None
    packets_sent: int
    packets_received: int

    # Multi-hop metrics (network path visibility) - always 3 hops
    hops: list[HopInfo] = field(default_factory=list)

    # DNS metrics (internet connectivity)
    dns_server: str = "unknown"
    dns_success: bool = False
    dns_latency_ms: float | None = None

    # Host environment info
    host_environment: HostEnvironment | None = None

    # Trace target used
    trace_target: str = DEFAULT_TRACE_TARGET

    def get_hop(self, hop_number: int) -> HopInfo | None:
        """Get hop by number (1-indexed)."""
        for hop in self.hops:
            if hop.hop_number == hop_number:
                return hop
        return None

    # Legacy compatibility properties
    @property
    def isp_hop_ip(self) -> str | None:
        """Legacy: Get ISP hop IP (hop 2)."""
        hop = self.get_hop(2)
        return hop.ip if hop else None

    @property
    def isp_hop_reachable(self) -> bool:
        """Legacy: Get ISP hop reachability (hop 2)."""
        hop = self.get_hop(2)
        return hop.reachable if hop else False

    @property
    def isp_hop_latency_ms(self) -> float | None:
        """Legacy: Get ISP hop latency (hop 2)."""
        hop = self.get_hop(2)
        return hop.latency_ms if hop else None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for coordinator data."""
        return {
            "gateway_ip": self.gateway_ip,
            "gateway_reachable": self.gateway_reachable,
            "gateway_latency_ms": self.gateway_latency_ms,
            "gateway_jitter_ms": self.gateway_jitter_ms,
            "packet_loss_percent": self.packet_loss_percent,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "hops": [hop.to_dict() for hop in self.hops],
            "dns_server": self.dns_server,
            "dns_success": self.dns_success,
            "dns_latency_ms": self.dns_latency_ms,
            "trace_target": self.trace_target,
            "host_environment": self.host_environment.to_dict() if self.host_environment else None,
        }


@dataclass
class NetworkDiagnosticsConfig:
    """Configuration for network diagnostics."""

    ping_count: int = DEFAULT_PING_COUNT
    ping_timeout: int = DEFAULT_PING_TIMEOUT
    dns_server: str = DEFAULT_DNS_SERVER
    dns_timeout: int = DEFAULT_DNS_TIMEOUT
    # Opt-in: send public hop IPs to Team Cymru to learn their owner (ADR-006)
    hop_ownership: bool = False
    # Off sends nothing for that kind: no pings, traceroutes or hop lookups; no DNS latency query
    monitor_gateway: bool = True
    monitor_dns: bool = True


class NetworkDiagnostics:
    """Network diagnostics for monitoring connection quality.

    Performs lightweight network checks including:
    - Gateway ping (auto-detected or configured)
    - 3-hop latency monitoring (gateway, ISP, backbone)
    - Per-hop jitter from consecutive ping round-trip times (ADR-009)
    - Packet loss tracking
    - DNS resolution timing
    - Reverse DNS names for detected hops

    Designed to run on its own polling interval, independent of other polling.
    """

    def __init__(
        self,
        config: NetworkDiagnosticsConfig | None = None,
        dns_server: str | None = None,
        ping_count: int | None = None,
        platform: Platform | None = None,
    ):
        """Initialize network diagnostics.

        Args:
            config: Configuration options. Uses defaults if not provided.
            dns_server: Override DNS server (alternative to config).
            ping_count: Override ping count (alternative to config).
            platform: OS probes; defaults to the running OS (platforms.get_platform).
        """
        self.config = config or NetworkDiagnosticsConfig()
        self._platform = platform or get_platform()

        # Allow simple overrides without full config
        if dns_server is not None:
            self.config.dns_server = dns_server
        if ping_count is not None:
            self.config.ping_count = ping_count

        # Gateway: read every poll, so a router that comes up late or changes is noticed
        self._gateway_ip: str | None = None

        # Hop info (hop_number -> ip); traced again every TRACE_RETRY_S while incomplete
        self._hop_ips: dict[int, str] = {}
        self._last_trace: float | None = None  # monotonic time of the last traceroute

        # Cached reverse DNS names (hop_number -> hostname)
        self._hop_hostnames: dict[int, str] = {}
        self._hostnames_collected = False
        self._hop_owners: dict[int, HopOwner] = {}

        # Host environment info
        self._host_environment: HostEnvironment | None = None

        # DNS server - resolved lazily on first run_diagnostics() to avoid blocking I/O in __init__
        self._dns_server: str | None = None
        self._dns_server_resolved = False

        # Trace target - resolved lazily based on DNS server
        self._trace_target: str | None = None

        # Everything sent since this instance was created (hosts keep their own running totals)
        self.counts = ProbeCounts()

    @property
    def platform(self) -> Platform:
        """The OS probes in use."""
        return self._platform

    async def _resolve_dns_server(self) -> str:
        """Resolve the DNS server to use.

        If config.dns_server is "auto", detect from system.
        Otherwise, use the configured value.

        Returns:
            DNS server IP to use for testing.
        """
        if self.config.dns_server == "auto":
            detected = await self._platform.system_dns()
            if detected:
                _LOGGER.info("Using system DNS server: %s", detected)
                return detected
            _LOGGER.warning(
                "Could not detect system DNS, falling back to %s",
                FALLBACK_DNS_SERVER,
            )
            return FALLBACK_DNS_SERVER
        if not is_ip(self.config.dns_server):  # it also becomes a traceroute target
            _LOGGER.warning("DNS server %r is not an IP address; using %s", self.config.dns_server, FALLBACK_DNS_SERVER)
            return FALLBACK_DNS_SERVER
        return self.config.dns_server

    def _resolve_trace_target(self) -> str:
        """Determine the traceroute target.

        Uses the DNS server if it's public, otherwise falls back to 8.8.8.8.
        This ensures we always trace to an external host to see the full path.

        Returns:
            IP address to use as traceroute target.
        """
        if self._dns_server and not is_private_ip(self._dns_server):
            _LOGGER.debug("Using DNS server as trace target: %s", self._dns_server)
            return self._dns_server

        _LOGGER.debug(
            "DNS server %s is private, using default trace target: %s",
            self._dns_server,
            DEFAULT_TRACE_TARGET,
        )
        return DEFAULT_TRACE_TARGET

    async def run_diagnostics(self) -> NetworkDiagnosticsResult:
        """Run all network diagnostics.

        Returns:
            NetworkDiagnosticsResult with all metrics.
        """
        # Resolve DNS server lazily on first run (to avoid blocking I/O in __init__)
        if not self._dns_server_resolved:
            self._dns_server = await self._resolve_dns_server()
            self._trace_target = self._resolve_trace_target()
            self._dns_server_resolved = True

        if self.config.monitor_gateway:
            await self._refresh_path()

        # Look up hop hostnames on first run (or after a cache reset)
        if self.config.monitor_gateway and self._hop_ips and not self._hostnames_collected:
            await self._collect_hostnames()
            self._hostnames_collected = True

        # Detect host environment on first run
        if not self._host_environment:
            self._host_environment = await self._detect_host_environment()

        # Run checks in parallel; monitoring switched off sends nothing
        gateway_task = self._check_gateway() if self.config.monitor_gateway else self._not_monitored_gateway()
        hops_task = self._check_all_hops() if self.config.monitor_gateway and self._hop_ips else self._empty_hops()
        if self.config.monitor_dns:
            self.counts.dns_queries += 1
            dns_task = self._check_dns()
        else:
            dns_task = self._not_monitored_dns()

        results = await asyncio.gather(gateway_task, hops_task, dns_task, return_exceptions=True)

        # Handle gateway result
        if isinstance(results[0], BaseException):
            _LOGGER.debug("Gateway check failed: %s", results[0])
            gateway_result: dict[str, Any] = {
                "reachable": False,
                "latency_ms": None,
                "jitter_ms": None,
                "packets_sent": self.config.ping_count,
                "packets_received": 0,
            }
        else:
            gateway_result = results[0]

        # Handle hops result
        if isinstance(results[1], BaseException):
            _LOGGER.debug("Hops check failed: %s", results[1])
            hops_result: list[HopInfo] = []
        else:
            hops_result = results[1]

        # Handle DNS result
        if isinstance(results[2], BaseException):
            _LOGGER.debug("DNS check failed: %s", results[2])
            dns_result: dict[str, Any] = {"success": False, "latency_ms": None}
        else:
            dns_result = results[2]

        gateway_jitter = gateway_result["jitter_ms"]

        # Calculate packet loss
        packet_loss = None
        if gateway_result["packets_sent"] > 0:
            packet_loss = (
                (gateway_result["packets_sent"] - gateway_result["packets_received"])
                / gateway_result["packets_sent"]
                * 100
            )

        result = NetworkDiagnosticsResult(
            timestamp=time.time(),
            gateway_ip=self._gateway_ip,
            gateway_reachable=gateway_result["reachable"],
            gateway_latency_ms=gateway_result["latency_ms"],
            gateway_jitter_ms=gateway_jitter,
            packet_loss_percent=packet_loss,
            packets_sent=gateway_result["packets_sent"],
            packets_received=gateway_result["packets_received"],
            hops=hops_result,
            dns_server=self._dns_server or "unknown",
            dns_success=dns_result["success"],
            dns_latency_ms=dns_result["latency_ms"],
            host_environment=self._host_environment,
            trace_target=self._trace_target or DEFAULT_TRACE_TARGET,
        )

        # Log summary
        hop_summary = (
            ", ".join(
                f"hop{h.hop_number}={'up' if h.reachable else 'down'}({format_ms(h.latency_ms)})" for h in hops_result
            )
            if hops_result
            else "no hops detected"
        )

        _LOGGER.debug(
            "Network diagnostics: gateway=%s (%s), %s, jitter=%s, loss=%s, dns=%s",
            "up" if result.gateway_reachable else "down",
            format_ms(result.gateway_latency_ms),
            hop_summary,
            format_ms(result.gateway_jitter_ms),
            "n/a" if result.packet_loss_percent is None else f"{result.packet_loss_percent:.1f}%",
            format_ms(result.dns_latency_ms),
        )

        return result

    async def _empty_hops(self) -> list[HopInfo]:
        """Return empty hops list."""
        return []

    async def _not_monitored_gateway(self) -> dict[str, Any]:
        """Gateway monitoring is off: nothing was sent, so nothing was lost."""
        return {"reachable": False, "latency_ms": None, "jitter_ms": None, "packets_sent": 0, "packets_received": 0}

    async def _not_monitored_dns(self) -> dict[str, Any]:
        """DNS monitoring is off: no query was sent."""
        return {"success": False, "latency_ms": None}

    async def _refresh_path(self) -> None:
        """Read the gateway (local and cheap) every poll; trace until all hops are known.

        A new gateway means a new path, so its hops are traced again. Missing hops
        are retried every TRACE_RETRY_S: after a power cut the host often boots
        before the router or modem is ready.
        """
        gateway = await self._platform.default_gateway()
        if gateway != self._gateway_ip:
            _LOGGER.info("Gateway is now %s (was %s)", gateway, self._gateway_ip)
            self._gateway_ip = gateway
            self.reset_hops()
        if self._gateway_ip and len(self._hop_ips) < NUM_HOPS and self._trace_due():
            hops = await self._detect_hops()
            if hops != self._hop_ips:
                self._hop_ips = hops
                self._hop_hostnames, self._hop_owners, self._hostnames_collected = {}, {}, False

    def _trace_due(self) -> bool:
        """No trace yet for this gateway, or TRACE_RETRY_S since the last one."""
        return self._last_trace is None or monotonic() - self._last_trace >= TRACE_RETRY_S

    async def _detect_hops(self) -> dict[int, str]:
        """Trace hops 1 to NUM_HOPS toward the trace target."""
        trace_target = self._trace_target or DEFAULT_TRACE_TARGET
        self.counts.traceroutes += 1
        self._last_trace = monotonic()
        hops = await self._platform.trace(trace_target, NUM_HOPS)
        if hops:
            _LOGGER.info(
                "Detected %d hops to %s: %s",
                len(hops),
                trace_target,
                ", ".join(f"hop{k}={v}" for k, v in sorted(hops.items())),
            )
        else:
            _LOGGER.warning("No hops detected toward %s; retrying in %d s", trace_target, TRACE_RETRY_S)
        return hops

    async def _check_all_hops(self) -> list[HopInfo]:
        """Ping all detected hops and collect latency info.

        Returns:
            List of HopInfo for each hop (always 3, with None for missing hops).
        """
        # Ping all detected hops in parallel
        tasks = []
        for hop_num in range(1, NUM_HOPS + 1):
            ip = self._hop_ips.get(hop_num)
            if ip:
                tasks.append(self._check_single_hop(hop_num, ip))
            else:
                tasks.append(self._create_missing_hop(hop_num))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        hops = []
        for i, result in enumerate(results):
            hop_num = i + 1
            if isinstance(result, BaseException):
                _LOGGER.debug("Hop %d check failed: %s", hop_num, result)
                hops.append(
                    HopInfo(
                        hop_number=hop_num,
                        ip=self._hop_ips.get(hop_num),
                        latency_ms=None,
                        jitter_ms=None,
                        reachable=False,
                        hostname=self._hop_hostnames.get(hop_num),
                        **self._owner_fields(hop_num),
                    )
                )
            else:
                hops.append(result)

        return hops

    async def _create_missing_hop(self, hop_number: int) -> HopInfo:
        """Create a HopInfo for a hop that wasn't detected."""
        return HopInfo(
            hop_number=hop_number,
            ip=None,
            latency_ms=None,
            jitter_ms=None,
            packet_loss_percent=None,
            packets_sent=0,
            packets_received=0,
            reachable=False,
        )

    async def _check_single_hop(self, hop_number: int, ip: str) -> HopInfo:
        """Ping a single hop multiple times and return HopInfo.

        Args:
            hop_number: The hop number (1, 2, 3)
            ip: The IP address to ping.

        Returns:
            HopInfo with latency, jitter, packet loss, and reachability.
        """
        packets_sent = self.config.ping_count
        packets_received, avg_latency, jitter = await self._ping_target(ip)

        # Calculate packet loss
        packet_loss = None
        if packets_sent > 0:
            packet_loss = ((packets_sent - packets_received) / packets_sent) * 100

        return HopInfo(
            hop_number=hop_number,
            ip=ip,
            latency_ms=avg_latency,
            jitter_ms=jitter,
            packet_loss_percent=packet_loss,
            packets_sent=packets_sent,
            packets_received=packets_received,
            reachable=packets_received > 0,
            hostname=self._hop_hostnames.get(hop_number),
            **self._owner_fields(hop_number),
        )

    async def _check_gateway(self) -> dict[str, Any]:
        """Ping the gateway multiple times and collect metrics.

        Returns:
            Dict with reachable, latency_ms, packets_sent, packets_received.
        """
        if not self._gateway_ip:
            return {
                "reachable": False,
                "latency_ms": None,
                "jitter_ms": None,
                "packets_sent": 0,
                "packets_received": 0,
            }

        packets_received, avg_latency, jitter = await self._ping_target(self._gateway_ip)

        return {
            "reachable": packets_received > 0,
            "latency_ms": avg_latency,
            "jitter_ms": jitter,
            "packets_sent": self.config.ping_count,
            "packets_received": packets_received,
        }

    async def _ping_target(self, host: str) -> tuple[int, float | None, float | None]:
        """Send ping_count pings one after another; return (replies, mean RTT, jitter).

        Jitter is the mean absolute difference between consecutive round-trip
        times in this poll (ADR-009).
        """
        replies = 0
        rtts: list[float] = []
        for _ in range(self.config.ping_count):
            replied, rtt = await self._single_ping(host)
            if replied:
                replies += 1
                if rtt is not None:
                    rtts.append(rtt)
        mean = sum(rtts) / len(rtts) if rtts else None
        return replies, mean, consecutive_jitter(rtts)

    async def check_gateway(self) -> bool:
        """One ping to the detected gateway, between polls (ADR-012); False if none was detected."""
        if not self._gateway_ip:
            return False
        ok, _ = await self._single_ping(self._gateway_ip)
        return ok

    async def check_internet(self) -> bool:
        """One DNS query to the server under test, between polls (ADR-012)."""
        self.counts.dns_queries += 1
        return bool((await self._check_dns())["success"])

    async def _single_ping(self, host: str) -> tuple[bool, float | None]:
        """Ping once; return (reply received, round-trip ms or None if not reported)."""
        self.counts.pings += 1
        return await self._platform.ping(host, self.config.ping_timeout)

    async def _check_dns(self) -> dict[str, Any]:
        """Time one query to the DNS server under test (dns_probe, R14)."""
        server = self._dns_server or FALLBACK_DNS_SERVER
        try:
            latency_ms = await dns_probe.query_time_ms(server, self.config.dns_timeout)
        except (OSError, ValueError) as e:
            _LOGGER.debug("DNS probe to %s failed: %s", server, e)
            latency_ms = None
        return {"success": latency_ms is not None, "latency_ms": latency_ms}

    def reset_gateway(self) -> None:
        """Reset cached gateway to force re-detection.

        Call this if you suspect the network configuration has changed.
        """
        self._gateway_ip = None

    def reset_hops(self) -> None:
        """Reset cached hop information to force re-detection.

        Call this if you suspect the network configuration has changed.
        """
        self._hop_ips = {}
        self._last_trace = None

    def detection_state(self) -> dict[str, Any]:
        """What has been detected and cached, for troubleshooting output."""
        return {
            "platform": self._platform.name,
            "gateway_detected": self._gateway_ip is not None,
            "hops_detected": len(self._hop_ips),
            "hostnames_collected": self._hostnames_collected,
            "trace_target": self._trace_target,
        }

    def reset_hostnames(self) -> None:
        """Clear cached hop hostnames, owners and host environment so all are re-detected."""
        self._hop_hostnames = {}
        self._hop_owners = {}
        self._hostnames_collected = False
        self._host_environment = None

    def reset_all(self) -> None:
        """Forget the gateway, hops, hostnames and DNS server, so the next poll detects all of them."""
        self.reset_gateway()
        self.reset_hops()
        self.reset_hostnames()
        self._dns_server_resolved = False

    # =========================================================================
    # Hop Hostnames
    # =========================================================================

    async def _collect_hostnames(self) -> None:
        """Look up reverse DNS names for all detected hops, in parallel."""
        hop_nums = list(self._hop_ips)
        self.counts.dns_queries += len(hop_nums)
        results = await asyncio.gather(
            *(self._reverse_dns_lookup(self._hop_ips[n]) for n in hop_nums),
            return_exceptions=True,
        )
        for hop_num, result in zip(hop_nums, results, strict=True):
            if isinstance(result, BaseException):
                _LOGGER.debug("Reverse DNS failed for hop %d: %s", hop_num, result)
            elif result:
                self._hop_hostnames[hop_num] = result
        if self.config.hop_ownership:
            await self._collect_owners()

    async def _collect_owners(self) -> None:
        """Look up who announces each public hop, through the DNS server under test."""
        server = self._dns_server or FALLBACK_DNS_SERVER
        hop_nums = list(self._hop_ips)
        results = await asyncio.gather(
            *(lookup_owner(self._hop_ips[n], server, self.config.dns_timeout) for n in hop_nums),
            return_exceptions=True,
        )
        for hop_num, result in zip(hop_nums, results, strict=True):
            # A public address costs one query, plus one for the AS name once an owner is found.
            if origin_query_name(self._hop_ips[hop_num]) is not None:
                self.counts.dns_queries += 1 + isinstance(result, HopOwner)
            if isinstance(result, BaseException):
                _LOGGER.debug("Owner lookup failed for hop %d: %s", hop_num, result)
            elif result:
                self._hop_owners[hop_num] = result

    def _owner_fields(self, hop_number: int) -> dict[str, Any]:
        """HopInfo fields for a hop's owner, empty when unknown."""
        owner = self._hop_owners.get(hop_number)
        return {"asn": owner.asn, "as_name": owner.name} if owner else {}

    async def _reverse_dns_lookup(self, ip: str) -> str | None:
        """Perform reverse DNS lookup for an IP address.

        Args:
            ip: The IP address to look up.

        Returns:
            Hostname if found, None otherwise.
        """
        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, socket.gethostbyaddr, ip),
                timeout=REVERSE_DNS_TIMEOUT_S,
            )
            hostname = result[0]
            if hostname == ip:
                # Some resolvers (Docker's among them) echo the address back
                return None
            _LOGGER.debug("Reverse DNS for %s: %s", ip, hostname)
            return hostname
        except (socket.herror, socket.gaierror):
            # No reverse DNS entry
            return None
        except TimeoutError:
            _LOGGER.debug("Reverse DNS timeout for %s", ip)
            return None

    async def _detect_host_environment(self) -> HostEnvironment:
        """Detect the host environment (connection type, container)."""
        env = await self._platform.host_environment()
        _LOGGER.info(
            "Host environment: connection=%s, interface=%s, container=%s",
            env.connection_type,
            env.interface_name,
            env.container_type or "native",
        )
        return env


# Convenience function for simple usage
async def run_network_diagnostics(
    dns_server: str = DEFAULT_DNS_SERVER,
) -> NetworkDiagnosticsResult:
    """Run network diagnostics with default settings.

    Convenience function for one-off diagnostics.

    Args:
        dns_server: DNS server to test against.

    Returns:
        NetworkDiagnosticsResult with all metrics.
    """
    config = NetworkDiagnosticsConfig(dns_server=dns_server)
    diagnostics = NetworkDiagnostics(config=config)
    return await diagnostics.run_diagnostics()
