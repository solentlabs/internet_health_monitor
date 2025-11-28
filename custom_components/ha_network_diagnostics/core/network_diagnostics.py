"""Network Diagnostics Module.

Provides lightweight network performance monitoring including:
- Gateway latency and reachability (local network)
- ISP first hop latency (connection to ISP)
- Jitter (latency variance)
- Packet loss percentage
- DNS resolution timing (internet connectivity)

Network path visualization:
    [HA Host] --Gateway Latency--> [Modem/Router] --ISP Latency--> [ISP Router] --DNS Latency--> [DNS Server]
              (local network)                      (your connection)            (internet)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import socket
import statistics
import time
from collections import deque
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

# Defaults
DEFAULT_PING_COUNT = 3
DEFAULT_PING_TIMEOUT = 2
DEFAULT_DNS_SERVER = "auto"  # Auto-detect from system
FALLBACK_DNS_SERVER = "1.1.1.1"  # Fallback if detection fails
DEFAULT_DNS_TIMEOUT = 5
DEFAULT_HISTORY_SIZE = 30  # Keep last 30 results for jitter calculation
RESOLV_CONF_PATH = "/etc/resolv.conf"


def _detect_system_dns_sync() -> str | None:
    """Detect the system's configured DNS server from /etc/resolv.conf.

    This is a synchronous function that performs blocking I/O.
    Use detect_system_dns() for async contexts.

    Returns:
        First nameserver IP found, or None if detection fails.
    """
    try:
        if not os.path.exists(RESOLV_CONF_PATH):
            _LOGGER.debug("resolv.conf not found at %s", RESOLV_CONF_PATH)
            return None

        with open(RESOLV_CONF_PATH) as f:
            content = f.read()

        # Parse nameserver lines
        # Format: nameserver <IP>
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("nameserver"):
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[1]
                    # Validate it looks like an IP (basic check)
                    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                        _LOGGER.debug("Detected system DNS: %s", ip)
                        return ip
                    # Also accept IPv6
                    if ":" in ip:
                        _LOGGER.debug("Detected system DNS (IPv6): %s", ip)
                        return ip

        _LOGGER.debug("No nameserver found in resolv.conf")
        return None

    except OSError as e:
        _LOGGER.debug("Error reading resolv.conf: %s", e)
        return None


async def detect_system_dns() -> str | None:
    """Detect the system's configured DNS server from /etc/resolv.conf.

    Async wrapper that runs blocking I/O in an executor.

    Returns:
        First nameserver IP found, or None if detection fails.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _detect_system_dns_sync)


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

    # ISP metrics (first hop outside local network)
    isp_hop_ip: str | None
    isp_hop_reachable: bool
    isp_hop_latency_ms: float | None

    # DNS metrics (internet connectivity)
    dns_server: str
    dns_success: bool
    dns_latency_ms: float | None

    def to_dict(self) -> dict:
        """Convert to dictionary for coordinator data."""
        return {
            "gateway_ip": self.gateway_ip,
            "gateway_reachable": self.gateway_reachable,
            "gateway_latency_ms": self.gateway_latency_ms,
            "gateway_jitter_ms": self.gateway_jitter_ms,
            "packet_loss_percent": self.packet_loss_percent,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "isp_hop_ip": self.isp_hop_ip,
            "isp_hop_reachable": self.isp_hop_reachable,
            "isp_hop_latency_ms": self.isp_hop_latency_ms,
            "dns_server": self.dns_server,
            "dns_success": self.dns_success,
            "dns_latency_ms": self.dns_latency_ms,
        }


@dataclass
class NetworkDiagnosticsConfig:
    """Configuration for network diagnostics."""

    ping_count: int = DEFAULT_PING_COUNT
    ping_timeout: int = DEFAULT_PING_TIMEOUT
    dns_server: str = DEFAULT_DNS_SERVER
    dns_timeout: int = DEFAULT_DNS_TIMEOUT
    history_size: int = DEFAULT_HISTORY_SIZE
    enable_isp_latency_check: bool = True  # Can be disabled if traceroute unavailable


class NetworkDiagnostics:
    """Network diagnostics for monitoring connection quality.

    Performs lightweight network checks including:
    - Gateway ping (auto-detected or configured)
    - Jitter calculation from ping history
    - Packet loss tracking
    - DNS resolution timing

    Designed to run on its own polling interval, independent of other polling.
    """

    def __init__(
        self,
        config: NetworkDiagnosticsConfig | None = None,
        dns_server: str | None = None,
        ping_count: int | None = None,
    ):
        """Initialize network diagnostics.

        Args:
            config: Configuration options. Uses defaults if not provided.
            dns_server: Override DNS server (alternative to config).
            ping_count: Override ping count (alternative to config).
        """
        self.config = config or NetworkDiagnosticsConfig()

        # Allow simple overrides without full config
        if dns_server is not None:
            self.config.dns_server = dns_server
        if ping_count is not None:
            self.config.ping_count = ping_count

        # History for jitter calculation
        self._latency_history: deque[float] = deque(maxlen=self.config.history_size)

        # Cached gateway
        self._gateway_ip: str | None = None
        self._gateway_detection_failed = False

        # Cached ISP hop (first hop outside local network)
        self._isp_hop_ip: str | None = None
        self._isp_hop_detection_failed = False

        # DNS server - resolved lazily on first run_diagnostics() to avoid blocking I/O in __init__
        self._dns_server: str | None = None
        self._dns_server_resolved = False

    async def _resolve_dns_server(self) -> str:
        """Resolve the DNS server to use.

        If config.dns_server is "auto", detect from system.
        Otherwise, use the configured value.

        Returns:
            DNS server IP to use for testing.
        """
        if self.config.dns_server == "auto":
            detected = await detect_system_dns()
            if detected:
                _LOGGER.info("Using system DNS server: %s", detected)
                return detected
            _LOGGER.warning(
                "Could not detect system DNS, falling back to %s",
                FALLBACK_DNS_SERVER,
            )
            return FALLBACK_DNS_SERVER
        return self.config.dns_server

    async def run_diagnostics(self) -> NetworkDiagnosticsResult:
        """Run all network diagnostics.

        Returns:
            NetworkDiagnosticsResult with all metrics.
        """
        # Resolve DNS server lazily on first run (to avoid blocking I/O in __init__)
        if not self._dns_server_resolved:
            self._dns_server = await self._resolve_dns_server()
            self._dns_server_resolved = True

        # Detect gateway if not cached
        if not self._gateway_ip and not self._gateway_detection_failed:
            self._gateway_ip = await self._detect_gateway()

        # Detect ISP hop if enabled and not cached (requires gateway to be detected first)
        if (
            self.config.enable_isp_latency_check
            and self._gateway_ip
            and not self._isp_hop_ip
            and not self._isp_hop_detection_failed
        ):
            self._isp_hop_ip = await self._detect_isp_hop()

        # Run checks in parallel
        gateway_task = self._check_gateway()
        # Only run ISP check if enabled
        if self.config.enable_isp_latency_check:
            isp_task = self._check_isp_hop()
        else:
            # Return disabled result immediately
            async def disabled_isp() -> dict:
                return {"reachable": False, "latency_ms": None}

            isp_task = disabled_isp()
        dns_task = self._check_dns()

        results = await asyncio.gather(gateway_task, isp_task, dns_task, return_exceptions=True)

        # Handle gateway result
        if isinstance(results[0], Exception):
            _LOGGER.debug("Gateway check failed: %s", results[0])
            gateway_result: dict = {
                "reachable": False,
                "latency_ms": None,
                "packets_sent": self.config.ping_count,
                "packets_received": 0,
            }
        else:
            gateway_result = results[0]  # type: ignore[assignment]

        # Handle ISP result
        if isinstance(results[1], Exception):
            _LOGGER.debug("ISP hop check failed: %s", results[1])
            isp_result: dict = {"reachable": False, "latency_ms": None}
        else:
            isp_result = results[1]  # type: ignore[assignment]

        # Handle DNS result
        if isinstance(results[2], Exception):
            _LOGGER.debug("DNS check failed: %s", results[2])
            dns_result: dict = {"success": False, "latency_ms": None}
        else:
            dns_result = results[2]  # type: ignore[assignment]

        # Calculate jitter from history
        jitter = self._calculate_jitter()

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
            gateway_jitter_ms=jitter,
            packet_loss_percent=packet_loss,
            packets_sent=gateway_result["packets_sent"],
            packets_received=gateway_result["packets_received"],
            isp_hop_ip=self._isp_hop_ip,
            isp_hop_reachable=isp_result["reachable"],
            isp_hop_latency_ms=isp_result["latency_ms"],
            dns_server=self._dns_server or "unknown",  # Use resolved DNS (actual IP, not "auto")
            dns_success=dns_result["success"],
            dns_latency_ms=dns_result["latency_ms"],
        )

        _LOGGER.debug(
            "Network diagnostics: gateway=%s (%.1fms), isp=%s (%.1fms), jitter=%.1fms, loss=%.1f%%, dns=%.1fms",
            "up" if result.gateway_reachable else "down",
            result.gateway_latency_ms or 0,
            "up" if result.isp_hop_reachable else "down",
            result.isp_hop_latency_ms or 0,
            result.gateway_jitter_ms or 0,
            result.packet_loss_percent or 0,
            result.dns_latency_ms or 0,
        )

        return result

    async def _detect_gateway(self) -> str | None:
        """Detect the default gateway IP address.

        Uses `ip route` on Linux to find the default gateway.

        Returns:
            Gateway IP address or None if detection fails.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "ip",
                "route",
                "show",
                "default",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode != 0:
                _LOGGER.debug("ip route command failed with code %d", proc.returncode)
                self._gateway_detection_failed = True
                return None

            output = stdout.decode().strip()
            # Parse: "default via 192.168.1.1 dev eth0 ..."
            parts = output.split()
            if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                gateway = parts[2]
                _LOGGER.debug("Detected gateway: %s", gateway)
                return gateway

            _LOGGER.debug("Could not parse gateway from: %s", output)
            self._gateway_detection_failed = True
            return None

        except Exception as e:
            _LOGGER.debug("Gateway detection error: %s", e)
            self._gateway_detection_failed = True
            return None

    async def _detect_isp_hop(self) -> str | None:  # noqa: C901
        """Detect the first hop outside the local network (ISP router).

        Uses traceroute to find the second hop (first hop after gateway).
        This is typically the first ISP router on the path to the internet.

        Returns:
            ISP hop IP address or None if detection fails.
        """
        try:
            # Use traceroute with max 3 hops (we only need the 2nd hop)
            # -n: numeric output (no DNS resolution for speed)
            # -q 1: only 1 query per hop (faster)
            # -w 2: 2 second timeout per probe
            proc = await asyncio.create_subprocess_exec(
                "traceroute",
                "-n",
                "-q",
                "1",
                "-w",
                "2",
                "-m",
                "3",  # max 3 hops
                "8.8.8.8",  # target (we don't need to reach it, just see the path)
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=10,  # Total timeout for traceroute
                )
            except TimeoutError:
                _LOGGER.debug("Traceroute timed out")
                proc.kill()
                self._isp_hop_detection_failed = True
                return None

            if proc.returncode is not None and proc.returncode != 0:
                # Check if traceroute is not available
                if b"not found" in stderr or b"No such file" in stderr:
                    _LOGGER.debug("traceroute command not available")
                    self._isp_hop_detection_failed = True
                    return None
                # Other errors - might still have partial output
                _LOGGER.debug("traceroute returned code %d", proc.returncode)

            output = stdout.decode().strip()
            _LOGGER.debug("Traceroute output:\n%s", output)

            # Parse traceroute output
            # Format: " 1  192.168.1.1  1.234 ms"
            #         " 2  10.0.0.1  5.678 ms"
            # or: " 1  192.168.1.1  1.234 ms"
            #     " 2  * * *" (timeout)
            lines = output.splitlines()

            for line in lines:
                line = line.strip()
                # Skip header line
                if line.startswith("traceroute"):
                    continue

                parts = line.split()
                if len(parts) < 2:
                    continue

                try:
                    hop_num = int(parts[0])
                except ValueError:
                    continue

                # We want hop 2 (first hop after gateway)
                if hop_num == 2:
                    # Check if it's a timeout (* * *)
                    if parts[1] == "*":
                        _LOGGER.debug("ISP hop (hop 2) timed out in traceroute")
                        self._isp_hop_detection_failed = True
                        return None

                    # Extract IP address
                    ip = parts[1]
                    # Validate it looks like an IP
                    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                        _LOGGER.debug("Detected ISP hop: %s", ip)
                        return ip
                    # Also accept IPv6
                    if ":" in ip:
                        _LOGGER.debug("Detected ISP hop (IPv6): %s", ip)
                        return ip

            _LOGGER.debug("Could not find ISP hop (hop 2) in traceroute output")
            self._isp_hop_detection_failed = True
            return None

        except FileNotFoundError:
            _LOGGER.debug("traceroute command not found")
            self._isp_hop_detection_failed = True
            return None
        except Exception as e:
            _LOGGER.debug("ISP hop detection error: %s", e)
            self._isp_hop_detection_failed = True
            return None

    async def _check_gateway(self) -> dict:
        """Ping the gateway multiple times and collect metrics.

        Returns:
            Dict with reachable, latency_ms, packets_sent, packets_received.
        """
        if not self._gateway_ip:
            return {
                "reachable": False,
                "latency_ms": None,
                "packets_sent": 0,
                "packets_received": 0,
            }

        latencies = []
        packets_received = 0

        for _ in range(self.config.ping_count):
            success, latency = await self._single_ping(self._gateway_ip)
            if success and latency is not None:
                latencies.append(latency)
                packets_received += 1

        # Calculate average latency
        avg_latency = None
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            # Add to history for jitter calculation
            self._latency_history.append(avg_latency)

        return {
            "reachable": packets_received > 0,
            "latency_ms": avg_latency,
            "packets_sent": self.config.ping_count,
            "packets_received": packets_received,
        }

    async def _check_isp_hop(self) -> dict:
        """Ping the ISP hop (first router outside local network).

        Returns:
            Dict with reachable and latency_ms.
        """
        if not self._isp_hop_ip:
            return {"reachable": False, "latency_ms": None}

        # Single ping to ISP hop (faster, less traffic)
        success, latency = await self._single_ping(self._isp_hop_ip)

        return {
            "reachable": success,
            "latency_ms": latency,
        }

    async def _single_ping(self, host: str) -> tuple[bool, float | None]:
        """Perform a single ICMP ping.

        Args:
            host: Target IP address or hostname.

        Returns:
            Tuple of (success, latency_ms or None).
        """
        try:
            start_time = time.time()

            proc = await asyncio.create_subprocess_exec(
                "ping",
                "-c",
                "1",
                "-W",
                str(self.config.ping_timeout),
                host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            latency_ms = (time.time() - start_time) * 1000
            success = proc.returncode == 0

            return success, latency_ms if success else None

        except Exception as e:
            _LOGGER.debug("Ping error for %s: %s", host, e)
            return False, None

    async def _check_dns(self) -> dict:
        """Check DNS resolution timing.

        Uses `dig` command for accurate DNS latency measurement.
        Falls back to socket.getaddrinfo if dig is not available.

        Returns:
            Dict with success and latency_ms.
        """
        # Try dig first for accurate measurement
        result = await self._check_dns_with_dig()
        if result["success"] or result.get("dig_available", True):
            return result

        # Fall back to socket-based resolution
        return await self._check_dns_with_socket()

    async def _check_dns_with_dig(self) -> dict:
        """Check DNS using dig command for accurate latency.

        Uses dig to query the configured DNS server directly.
        Queries a random subdomain to bypass DNS caching at all levels
        (local resolver, upstream DNS, etc.) for accurate RTT measurement.

        Returns:
            Dict with success, latency_ms, and dig_available flag.
        """
        try:
            # Use a random subdomain to bypass DNS caching
            # The subdomain won't exist, but we still get accurate RTT
            # from the NXDOMAIN response after full resolution
            # Prefix with "_ha-nd-" (Home Assistant Network Diagnostics)
            # so network admins can identify the source of these queries
            import uuid

            random_suffix = uuid.uuid4().hex[:8]
            test_hostname = f"_ha-nd-{random_suffix}.cloudflare.com"

            proc = await asyncio.create_subprocess_exec(
                "dig",
                f"@{self._dns_server}",
                test_hostname,
                "+noall",
                "+stats",
                "+time=3",  # 3 second timeout
                "+tries=1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.dns_timeout,
            )

            if proc.returncode != 0:
                _LOGGER.debug("dig command failed: %s", stderr.decode())
                return {"success": False, "latency_ms": None, "dig_available": True}

            # Parse dig output for query time
            # Format: ";; Query time: 23 msec"
            output = stdout.decode()
            for line in output.splitlines():
                if "Query time:" in line:
                    # Extract milliseconds: ";; Query time: 23 msec"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "time:" and i + 1 < len(parts):
                            try:
                                latency_ms = float(parts[i + 1])
                                return {"success": True, "latency_ms": latency_ms}
                            except ValueError:
                                pass

            _LOGGER.debug("Could not parse dig output: %s", output)
            return {"success": False, "latency_ms": None, "dig_available": True}

        except FileNotFoundError:
            _LOGGER.debug("dig command not found, falling back to socket")
            return {"success": False, "latency_ms": None, "dig_available": False}
        except TimeoutError:
            _LOGGER.debug("dig command timed out")
            return {"success": False, "latency_ms": None, "dig_available": True}
        except Exception as e:
            _LOGGER.debug("dig error: %s", e)
            return {"success": False, "latency_ms": None, "dig_available": True}

    async def _check_dns_with_socket(self) -> dict:
        """Check DNS using socket.getaddrinfo (fallback).

        Note: This goes through the system resolver and may return
        cached results, showing lower latency than actual DNS RTT.

        Returns:
            Dict with success and latency_ms.
        """
        try:
            test_hostname = "cloudflare.com"
            start_time = time.time()

            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: socket.getaddrinfo(
                        test_hostname,
                        None,
                        socket.AF_INET,
                        socket.SOCK_STREAM,
                    ),
                ),
                timeout=self.config.dns_timeout,
            )

            latency_ms = (time.time() - start_time) * 1000

            return {"success": True, "latency_ms": latency_ms}

        except TimeoutError:
            _LOGGER.debug("DNS resolution timed out")
            return {"success": False, "latency_ms": None}
        except socket.gaierror as e:
            _LOGGER.debug("DNS resolution failed: %s", e)
            return {"success": False, "latency_ms": None}
        except Exception as e:
            _LOGGER.debug("DNS check error: %s", e)
            return {"success": False, "latency_ms": None}

    def _calculate_jitter(self) -> float | None:
        """Calculate jitter from latency history.

        Jitter is the standard deviation of recent latency measurements.

        Returns:
            Jitter in milliseconds, or None if insufficient data.
        """
        if len(self._latency_history) < 2:
            return None

        try:
            return statistics.stdev(self._latency_history)
        except statistics.StatisticsError:
            return None

    def clear_history(self) -> None:
        """Clear the latency history.

        Useful for resetting jitter calculation after configuration changes.
        """
        self._latency_history.clear()

    def reset_gateway(self) -> None:
        """Reset cached gateway to force re-detection.

        Call this if you suspect the network configuration has changed.
        """
        self._gateway_ip = None
        self._gateway_detection_failed = False

    def reset_isp_hop(self) -> None:
        """Reset cached ISP hop to force re-detection.

        Call this if you suspect the network configuration has changed.
        """
        self._isp_hop_ip = None
        self._isp_hop_detection_failed = False

    def reset_all(self) -> None:
        """Reset all cached network information.

        Clears gateway, ISP hop, and latency history.
        """
        self.reset_gateway()
        self.reset_isp_hop()
        self.clear_history()


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
