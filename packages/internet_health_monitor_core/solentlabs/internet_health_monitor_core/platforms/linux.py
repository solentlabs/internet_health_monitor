"""Linux probes: `ip`, `ping`, `traceroute`, /etc/resolv.conf and /proc."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil

from ..timing import PING_PROCESS_GRACE_S, TRACE_PROBE_TIMEOUT_S
from .base import ConnectionType, HostEnvironment, is_ip

_LOGGER = logging.getLogger(__name__)

RESOLV_CONF_PATH = "/etc/resolv.conf"
# Without these, IHM finds no gateway and measures nothing. traceroute is
# optional: without it only hops go missing.
REQUIRED_TOOLS = ("ip", "ping")
OPTIONAL_TOOLS = ("traceroute",)

# ping's summary line: iputils "rtt min/avg/max/mdev = a/b/c/d ms",
# BusyBox "round-trip min/avg/max = a/b/c ms". Same shapes as HA core's
# ping matchers (docs/REFERENCES.md § R10).
_PING_SUMMARY_RE = re.compile(r"min/avg/max\S* = (\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)")

_WIFI_PREFIXES = ("wlan", "wlp", "wifi", "wl")
_ETHERNET_PREFIXES = ("eth", "enp", "eno", "ens")


def parse_ping_rtt_ms(output: str) -> float | None:
    """Return the average round-trip time ping reported, or None if absent."""
    match = _PING_SUMMARY_RE.search(output)
    return float(match.group(2)) if match else None


def parse_traceroute_hops(output: str, max_hops: int) -> dict[int, str]:
    """Return {hop number: IP} for hops 1 to max_hops in `traceroute -n` output."""
    # Lines look like " 1  192.168.1.1  1.234 ms", or " 2  *" on a timeout.
    hops: dict[int, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        hop_num = int(parts[0])
        if hop_num > max_hops:
            break
        ip = parts[1]
        if ip == "*":
            _LOGGER.debug("Hop %d timed out", hop_num)
        elif is_ip(ip):
            hops[hop_num] = ip
            _LOGGER.debug("Detected hop %d: %s", hop_num, ip)
    return hops


def parse_default_route(output: str) -> tuple[str | None, str | None]:
    """Return (gateway, interface) from `ip route show default` output."""
    # "default via 192.168.1.1 dev eth0 proto dhcp ..."
    parts = output.split()
    gateway = parts[2] if len(parts) >= 3 and parts[:2] == ["default", "via"] and is_ip(parts[2]) else None
    interface = None
    for i, part in enumerate(parts[:-1]):
        if part == "dev":
            interface = parts[i + 1]
            break
    return gateway, interface


def parse_resolv_conf(content: str) -> str | None:
    """Return the first nameserver address in resolv.conf content."""
    for line in content.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "nameserver" and is_ip(parts[1]):
            return parts[1]
    return None


def classify_interface(interface: str | None) -> ConnectionType:
    """Return the connection type an interface name indicates."""
    if not interface:
        return "unknown"
    if interface.startswith(_WIFI_PREFIXES):
        return "wifi"
    if interface.startswith(_ETHERNET_PREFIXES):
        return "ethernet"
    if interface.startswith(("docker", "br-")):
        return "bridge"
    if interface.startswith("veth"):
        return "veth"
    return "unknown"


async def _run(*args: str, timeout: float) -> tuple[int | None, str, str]:
    """Run a command; return (exit code, stdout, stderr). Raises FileNotFoundError if missing."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        raise
    return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")


def _read_text(path: str) -> str | None:
    """Return a file's text, or None if it cannot be read."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _detect_container() -> str | None:
    """Return the container type, or None when running natively."""
    if os.path.exists("/.dockerenv"):
        return "docker"
    cgroup = _read_text("/proc/1/cgroup") or ""
    if "docker" in cgroup:
        return "docker"
    if "podman" in cgroup or os.path.exists("/run/.containerenv"):
        return "podman"
    if "container=lxc" in (_read_text("/proc/1/environ") or ""):
        return "lxc"
    return None


class LinuxPlatform:
    """Probes for Linux, including HA OS and containers (iputils or BusyBox)."""

    name = "linux"

    def missing_tools(self) -> list[str]:
        """Return the required commands not found on PATH."""
        return [tool for tool in REQUIRED_TOOLS if shutil.which(tool) is None]

    def missing_optional_tools(self) -> list[str]:
        """Return the optional commands not found on PATH (traceroute: hops 2 and 3)."""
        return [tool for tool in OPTIONAL_TOOLS if shutil.which(tool) is None]

    async def default_gateway(self) -> str | None:
        """Return the gateway from `ip route show default`."""
        try:
            code, out, _ = await _run("ip", "route", "show", "default", timeout=5)
        except (OSError, TimeoutError) as e:
            _LOGGER.debug("Gateway detection error: %s", e)
            return None
        gateway, _ = parse_default_route(out) if code == 0 else (None, None)
        if gateway:
            _LOGGER.debug("Detected gateway: %s", gateway)
        else:
            _LOGGER.debug("No gateway in `ip route` output: %s", out.strip())
        return gateway

    async def system_dns(self) -> str | None:
        """Return the first nameserver in /etc/resolv.conf."""
        content = await asyncio.get_running_loop().run_in_executor(None, _read_text, RESOLV_CONF_PATH)
        server = parse_resolv_conf(content) if content else None
        _LOGGER.debug("Detected system DNS: %s", server)
        return server

    async def ping(self, host: str, timeout_s: int) -> tuple[bool, float | None]:
        """Ping once; latency is ping's own round-trip time (R10), not process wall-clock."""
        if not is_ip(host):  # never let text become a ping option
            _LOGGER.warning("Not pinging %r: not an IP address", host)
            return False, None
        try:
            code, out, _ = await _run(
                "ping", "-c", "1", "-W", str(timeout_s), host, timeout=timeout_s + PING_PROCESS_GRACE_S
            )
        except (OSError, TimeoutError) as e:
            _LOGGER.debug("Ping error for %s: %s", host, e)
            return False, None
        if code != 0:
            return False, None
        rtt = parse_ping_rtt_ms(out)
        if rtt is None:
            _LOGGER.debug("Ping reply from %s had no round-trip time in its output", host)
        return True, rtt

    async def trace(self, target: str, max_hops: int) -> dict[int, str]:
        """Run `traceroute -n -q 1 -w <probe timeout> -m <max_hops>`."""
        if not is_ip(target):  # never let text become a traceroute option
            _LOGGER.warning("Not tracing %r: not an IP address", target)
            return {}
        try:
            _, out, _ = await _run(
                "traceroute",
                "-n",
                "-q",
                "1",
                "-w",
                str(TRACE_PROBE_TIMEOUT_S),
                "-m",
                str(max_hops),
                target,
                timeout=max_hops * (TRACE_PROBE_TIMEOUT_S + 1) + PING_PROCESS_GRACE_S,
            )
        except FileNotFoundError:
            _LOGGER.debug("traceroute command not found")
            return {}
        except (OSError, TimeoutError) as e:
            _LOGGER.debug("Traceroute error: %s", e)
            return {}
        _LOGGER.debug("Traceroute to %s: %s", target, " | ".join(line.strip() for line in out.splitlines()))
        return parse_traceroute_hops(out, max_hops)

    async def host_environment(self) -> HostEnvironment:
        """Detect connection type and container."""
        loop = asyncio.get_running_loop()
        interface = None
        try:
            code, out, _ = await _run("ip", "route", "show", "default", timeout=5)
            if code == 0:
                _, interface = parse_default_route(out)
        except (OSError, TimeoutError) as e:
            _LOGGER.debug("Connection type detection error: %s", e)
        return HostEnvironment(
            connection_type=classify_interface(interface),
            interface_name=interface,
            container_type=await loop.run_in_executor(None, _detect_container),
        )
