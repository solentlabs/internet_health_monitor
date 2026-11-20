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


# Speed tests (docs/SPEED_TEST_BACKENDS.md § How IHM Measures).
# Seconds each direction is loaded; ndt7 tests run "up to ten seconds" (R9).
SPEED_TEST_DIRECTION_S = 10.0
# Seconds at the start of each direction left out of throughput while TCP ramps up.
SPEED_TEST_WARMUP_S = 1.5
# Seconds between loaded-latency probes (Cloudflare's spacing, R5).
SPEED_TEST_PROBE_INTERVAL_S = 0.4
# Seconds between checks of a running direction's data limit.
SPEED_TEST_LIMIT_CHECK_S = 0.05
# NDT7: a client may close a test that has run this long (R9).
SPEED_TEST_NDT7_MAX_S = 13.0
# NDT7: seconds to wait after an upload for the server's last measurements before closing.
SPEED_TEST_NDT7_CLOSE_GRACE_S = 1.0
# Seconds before a whole speed test is abandoned.
SPEED_TEST_TIMEOUT_S = 60.0
# Seconds to wait for one request that is not a load stream (lookups, probes).
SPEED_TEST_REQUEST_TIMEOUT_S = 10.0
# Per-test data limit in MB, both directions together; each direction stops at half.
SPEED_TEST_DATA_LIMIT_MB_DEFAULT = 500
SPEED_TEST_DATA_LIMIT_MB_MIN = 100
SPEED_TEST_DATA_LIMIT_MB_MAX = 10000
# Tests allowed in any SPEED_TEST_DAILY_WINDOW_S, manual or automated. Default 4:
# M-Lab's limit for automated clients (R9). Max 40: its limit for interactive users.
SPEED_TEST_DAILY_DEFAULT = 4
SPEED_TEST_DAILY_MIN = 1
SPEED_TEST_DAILY_MAX = 40
SPEED_TEST_DAILY_WINDOW_S = 24 * 3600
# M-Lab's AUP: automated clients "should not run more than 4 tests per day, and test
# times should be randomized" (R9). A run no person started counts toward this cap,
# whatever the daily limit, and waits a random time up to the maximum before starting.
# M-Lab names no window; one hour is IHM's choice (docs/SPEED_TEST_BACKENDS.md § Limits).
SPEED_TEST_MLAB_AUTOMATED_DAILY = 4
SPEED_TEST_MLAB_AUTOMATED_WAIT_MAX_S = 3600
# The daily automatic test starts at a random time in this local window: overnight,
# when the household is least likely to be on a call or a game (docs/SPEED_TEST_BACKENDS.md
# § Limits), and random so homes don't all test at once (M-Lab, R9).
SPEED_TEST_AUTO_START_HOUR = 1
SPEED_TEST_AUTO_WINDOW_S = 4 * 3600
# Speed test data budget, in GB per SPEED_TEST_BUDGET_WINDOW_S; 0 means none.
SPEED_TEST_BUDGET_GB_DEFAULT = 0
SPEED_TEST_BUDGET_GB_MAX = 10000
SPEED_TEST_BUDGET_WINDOW_S = 30 * 24 * 3600

# Hosts that keep running usage totals write probe counts within this many seconds
# (and on unload); speed test totals are written at once.
USAGE_SAVE_DELAY_S = 300

# Reachability (ADR-012): a failure turns a target off only after this many quick
# checks also fail, this far apart; while off, it is re-checked this often. While
# healthy, nothing runs between polls.
REACHABILITY_CONFIRM_CHECKS = 2
REACHABILITY_CONFIRM_INTERVAL_S = 5.0
REACHABILITY_DOWN_RECHECK_S = 10.0

# Seconds between traceroutes while fewer than three hops are known. IHM's choice:
# a modem can take minutes to sync after a power cut, and one trace is a few packets.
TRACE_RETRY_S = 600
