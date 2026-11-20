"""Tests for the Linux probes: parsers on captured output, commands mocked."""

from __future__ import annotations

import os
import shutil
import sys
from unittest.mock import AsyncMock, patch

import pytest

from solentlabs.internet_health_monitor_core.platforms import linux
from solentlabs.internet_health_monitor_core.platforms.linux import (
    LinuxPlatform,
    classify_interface,
    parse_default_route,
    parse_ping_rtt_ms,
    parse_resolv_conf,
    parse_traceroute_hops,
)

# Ping output -> round-trip time (ms) reported by ping itself.
# Summary formats follow HA core's ping matchers (REFERENCES.md § R10).
# fmt: off
PING_RTT_CASES = [
    # (description, output, expected_ms)
    (
        "iputils summary",
        "PING 192.168.1.1 (192.168.1.1) 56(84) bytes of data.\n"
        "64 bytes from 192.168.1.1: icmp_seq=1 ttl=64 time=0.512 ms\n\n"
        "--- 192.168.1.1 ping statistics ---\n"
        "1 packets transmitted, 1 received, 0% packet loss, time 0ms\n"
        "rtt min/avg/max/mdev = 0.512/0.512/0.512/0.000 ms\n",
        0.512,
    ),
    (
        "busybox summary",
        "PING 192.168.1.1 (192.168.1.1): 56 data bytes\n"
        "64 bytes from 192.168.1.1: seq=0 ttl=64 time=12.345 ms\n\n"
        "--- 192.168.1.1 ping statistics ---\n"
        "1 packets transmitted, 1 packets received, 0% packet loss\n"
        "round-trip min/avg/max = 12.345/12.345/12.345 ms\n",
        12.345,
    ),
    (
        "avg is used, not min or max",
        "rtt min/avg/max/mdev = 1.000/2.500/4.000/1.000 ms\n",
        2.5,
    ),
    (
        "no reply, no summary",
        "1 packets transmitted, 0 received, 100% packet loss, time 0ms\n",
        None,
    ),
    ("empty output", "", None),
]
# fmt: on


# traceroute -n output -> {hop number: IP}, hops 1-3 only.
# fmt: off
TRACEROUTE_CASES = [
    # (description, output, expected)
    (
        "three hops",
        "traceroute to 8.8.8.8 (8.8.8.8), 3 hops max, 46 byte packets\n"
        " 1  192.168.1.1  0.512 ms\n 2  10.0.0.1  8.1 ms\n 3  198.51.100.1  12.0 ms\n",
        {1: "192.168.1.1", 2: "10.0.0.1", 3: "198.51.100.1"},
    ),
    (
        "timeouts skipped",
        " 1  172.19.0.1  0.007 ms\n 2  *\n 3  *\n",
        {1: "172.19.0.1"},
    ),
    (
        "hops past 3 ignored",
        " 1  192.168.1.1  1 ms\n 4  203.0.113.4  20 ms\n",
        {1: "192.168.1.1"},
    ),
    ("IPv6 hop", " 1  fe80::1  0.5 ms\n", {1: "fe80::1"}),
    ("non-IP token skipped", " 1  gateway.lan  0.5 ms\n", {}),
    ("empty output", "", {}),
]
# fmt: on



# `ip route show default` output -> (gateway, interface)
# fmt: off
ROUTE_CASES = [
    ("gateway and device", "default via 192.168.1.1 dev eth0 proto dhcp metric 100", ("192.168.1.1", "eth0")),
    ("device only",        "default dev wg0 scope link",                              (None, "wg0")),
    ("no default route",   "",                                                        (None, None)),
]

# resolv.conf content -> first nameserver
RESOLV_CASES = [
    ("first of two",     "nameserver 8.8.8.8\nnameserver 8.8.4.4\n",       "8.8.8.8"),
    ("comments skipped", "# nameserver 9.9.9.9\nsearch lan\nnameserver 1.1.1.1\n", "1.1.1.1"),
    ("IPv6",             "nameserver fd00::1\n",                             "fd00::1"),
    ("none",             "search lan\n",                                     None),
]

# interface name -> connection type
INTERFACE_CASES = [
    ("wlan0", "wifi"), ("wlp2s0", "wifi"), ("eth0", "ethernet"), ("enp3s0", "ethernet"),
    ("docker0", "bridge"), ("br-1a2b", "bridge"), ("veth12", "veth"), ("wg0", "unknown"), (None, "unknown"),
]

# (exit code, stdout) from `ping -c 1` -> (replied, rtt)
PING_CASES = [
    ("reply",            0, "rtt min/avg/max/mdev = 3.210/3.210/3.210/0.000 ms\n", (True, 3.21)),
    ("reply without rtt", 0, "unrecognized output\n",                              (True, None)),
    ("no reply",         1, "",                                                     (False, None)),
]
# fmt: on


@pytest.mark.parametrize(("description", "output", "expected"), TRACEROUTE_CASES, ids=[c[0] for c in TRACEROUTE_CASES])
def test_parse_traceroute_hops(description: str, output: str, expected: dict[int, str]) -> None:
    """Hop IPs come from numeric traceroute lines, hops 1-3, timeouts skipped."""
    assert parse_traceroute_hops(output, 3) == expected


@pytest.mark.parametrize(("description", "output", "expected"), PING_RTT_CASES, ids=[c[0] for c in PING_RTT_CASES])
def test_parse_ping_rtt_ms(description: str, output: str, expected: float | None) -> None:
    """Round-trip time comes from ping's own summary line."""
    assert parse_ping_rtt_ms(output) == expected


@pytest.mark.parametrize(("description", "output", "expected"), ROUTE_CASES, ids=[c[0] for c in ROUTE_CASES])
def test_parse_default_route(description: str, output: str, expected: tuple[str | None, str | None]) -> None:
    """Gateway follows `via`, interface follows `dev`."""
    assert parse_default_route(output) == expected


@pytest.mark.parametrize(("description", "content", "expected"), RESOLV_CASES, ids=[c[0] for c in RESOLV_CASES])
def test_parse_resolv_conf(description: str, content: str, expected: str | None) -> None:
    """The first valid nameserver line wins."""
    assert parse_resolv_conf(content) == expected


@pytest.mark.parametrize(("interface", "expected"), INTERFACE_CASES)
def test_classify_interface(interface: str | None, expected: str) -> None:
    """Interface name prefixes map to connection types."""
    assert classify_interface(interface) == expected


@pytest.mark.parametrize(("description", "code", "stdout", "expected"), PING_CASES, ids=[c[0] for c in PING_CASES])
async def test_ping(description: str, code: int, stdout: str, expected: tuple[bool, float | None]) -> None:
    """A zero exit is a reply; its RTT comes from the summary line."""
    with patch.object(linux, "_run", AsyncMock(return_value=(code, stdout, ""))):
        assert await LinuxPlatform().ping("192.168.1.1", 2) == expected


async def test_ping_missing_command() -> None:
    """No ping binary means no reply, not a crash."""
    with patch.object(linux, "_run", AsyncMock(side_effect=FileNotFoundError)):
        assert await LinuxPlatform().ping("192.168.1.1", 2) == (False, None)


@pytest.mark.parametrize(
    ("code", "stdout", "expected"), [(0, "default via 192.168.1.1 dev eth0", "192.168.1.1"), (1, "", None)]
)
async def test_default_gateway(code: int, stdout: str, expected: str | None) -> None:
    """Gateway comes from `ip route`; a failed command gives None."""
    with patch.object(linux, "_run", AsyncMock(return_value=(code, stdout, ""))):
        assert await LinuxPlatform().default_gateway() == expected


@pytest.mark.parametrize("error", [FileNotFoundError, TimeoutError])
async def test_trace_unavailable(error: type[Exception]) -> None:
    """Missing or hung traceroute gives no hops."""
    with patch.object(linux, "_run", AsyncMock(side_effect=error)):
        assert await LinuxPlatform().trace("8.8.8.8", 3) == {}


async def test_trace_parses_output() -> None:
    """Trace returns the parsed hops."""
    with patch.object(linux, "_run", AsyncMock(return_value=(0, TRACEROUTE_CASES[0][1], ""))):
        assert await LinuxPlatform().trace("8.8.8.8", 3) == TRACEROUTE_CASES[0][2]


async def test_system_dns(tmp_path) -> None:
    """System DNS is the first nameserver in resolv.conf; a missing file gives None."""
    conf = tmp_path / "resolv.conf"
    conf.write_text("nameserver 9.9.9.9\n")
    with patch.object(linux, "RESOLV_CONF_PATH", str(conf)):
        assert await LinuxPlatform().system_dns() == "9.9.9.9"
    with patch.object(linux, "RESOLV_CONF_PATH", str(tmp_path / "missing")):
        assert await LinuxPlatform().system_dns() is None


async def test_host_environment() -> None:
    """Connection type comes from the default route's interface."""
    with (
        patch.object(linux, "_run", AsyncMock(return_value=(0, "default via 192.168.1.1 dev wlan0", ""))),
        patch.object(linux, "_detect_container", return_value=None),
    ):
        env = await LinuxPlatform().host_environment()
    assert (env.connection_type, env.interface_name, env.container_type) == ("wifi", "wlan0", None)


# Marker files present -> container type
# fmt: off
ENVIRONMENT_CASES = [
    ("native",        set(),                  "",               "",              None),
    ("docker",        {"/.dockerenv"},        "",               "",              "docker"),
    ("docker cgroup", set(),                  "0::/docker/abc", "",              "docker"),
    ("podman",        {"/run/.containerenv"}, "",               "",              "podman"),
    ("lxc",           set(),                  "",               "container=lxc", "lxc"),
]
# fmt: on


@pytest.mark.parametrize(
    ("description", "files", "cgroup", "environ", "expected"), ENVIRONMENT_CASES, ids=[c[0] for c in ENVIRONMENT_CASES]
)
def test_detect_environment(description: str, files: set[str], cgroup: str, environ: str, expected: str | None) -> None:
    """Container type comes from marker files and /proc."""
    texts = {"/proc/1/cgroup": cgroup, "/proc/1/environ": environ}
    with (
        patch.object(os.path, "exists", side_effect=lambda p: p in files),
        patch.object(linux, "_read_text", side_effect=lambda p: texts.get(p)),
        patch.dict(os.environ, {}, clear=True),
    ):
        assert linux._detect_container() == expected


async def test_run_returns_exit_code_and_output() -> None:
    """_run captures a real (local, non-network) process."""
    code, out, _ = await linux._run(sys.executable, "-c", "print('ok')", timeout=10)
    assert (code, out.strip()) == (0, "ok")


async def test_run_kills_on_timeout() -> None:
    """A hung command is killed and the timeout raised."""
    with pytest.raises(TimeoutError):
        await linux._run(sys.executable, "-c", "import time; time.sleep(5)", timeout=0.2)


def test_read_text_missing(tmp_path) -> None:
    """An unreadable file gives None."""
    assert linux._read_text(str(tmp_path / "missing")) is None


# commands on PATH -> missing required tools
# fmt: off
MISSING_TOOL_CASES = [
    ("all present",    {"ip", "ping", "traceroute"}, []),
    ("no traceroute",  {"ip", "ping"},               []),
    ("no ping",        {"ip"},                       ["ping"]),
    ("nothing",        set(),                        ["ip", "ping"]),
]
# fmt: on


@pytest.mark.parametrize(
    ("description", "present", "expected"), MISSING_TOOL_CASES, ids=[c[0] for c in MISSING_TOOL_CASES]
)
def test_missing_tools(description: str, present: set[str], expected: list[str]) -> None:
    """ip and ping are required; traceroute is optional."""
    with patch.object(shutil, "which", side_effect=lambda tool: f"/bin/{tool}" if tool in present else None):
        assert LinuxPlatform().missing_tools() == expected
        assert LinuxPlatform().missing_optional_tools() == ([] if "traceroute" in present else ["traceroute"])
