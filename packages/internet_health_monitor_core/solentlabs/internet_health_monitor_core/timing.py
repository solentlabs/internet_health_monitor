"""Every interval, timeout and limit in Core, in one place (ADR-007).

Hosts read these instead of choosing their own: the HA integration polls every
POLL_INTERVAL_S, and its form and the CLI accept PING_COUNT_MIN..PING_COUNT_MAX.
"""

from __future__ import annotations

# Poll cadence. 60 s: docs/ARCHITECTURE_DECISIONS.md § ADR-007, sources R16.
POLL_INTERVAL_S = 60

# Pings per target per poll; sent one after another.
DEFAULT_PING_COUNT = 3
PING_COUNT_MIN = 1
PING_COUNT_MAX = 10

# Seconds to wait for one echo reply (ping -W, IcmpSendEcho timeout).
DEFAULT_PING_TIMEOUT = 2
# Extra seconds before a ping process that has not exited is killed.
PING_PROCESS_GRACE_S = 3
# Seconds to wait for each trace probe (traceroute -w, IcmpSendEcho per TTL).
TRACE_PROBE_TIMEOUT_S = 2
# Seconds to wait for one DNS reply (latency probe and hop ownership).
DEFAULT_DNS_TIMEOUT = 5
# Seconds to wait for one reverse DNS lookup.
REVERSE_DNS_TIMEOUT_S = 5


def steady_poll_bound_s(ping_count: int = PING_COUNT_MAX) -> int:
    """Longest a regular poll can take: the slowest target, since targets run in parallel.

    Each target's pings run one after another, each bounded by its timeout plus
    the process grace; the DNS probe runs alongside. Detection (traceroute,
    hostnames, ownership) runs only on the first poll and after a reset.
    """
    pings = ping_count * (DEFAULT_PING_TIMEOUT + PING_PROCESS_GRACE_S)
    return max(pings, DEFAULT_DNS_TIMEOUT)
