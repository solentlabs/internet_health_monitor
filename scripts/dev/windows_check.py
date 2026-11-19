"""Run Core's CLI once on the Windows host's Python (from WSL) and check the result.

Exercises the Windows probes for real: IP Helper calls, ping, trace. Sends one
ping per target and three trace probes; no speed test. Needs WSL interop and a
Windows `python.exe` (3.12+) on PATH. Nothing is installed on Windows.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / "packages" / "internet_health_monitor_core"


def main() -> int:
    """Run the check; return 0 when the gateway answered and at least one hop was traced."""
    if not shutil.which("python.exe") or not shutil.which("wslpath"):
        print("Skipped: needs WSL with a Windows python.exe on PATH")
        return 0
    win_path = subprocess.run(
        ["wslpath", "-w", str(PACKAGE)], capture_output=True, text=True, check=True
    ).stdout.strip()
    env = dict(os.environ, PYTHONPATH=win_path, WSLENV="PYTHONPATH/w")
    run = subprocess.run(
        ["python.exe", "-m", "solentlabs.internet_health_monitor_core", "--ping-count", "1"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    if run.returncode != 0:
        print(run.stderr or run.stdout)
        return 1
    result = json.loads(run.stdout)
    hops = [h for h in result["hops"] if h["ip"]]
    print(f"gateway reachable={result['gateway_reachable']} latency={result['gateway_latency_ms']} ms")
    print(f"hops traced={len(hops)} dns ok={result['dns_success']}")
    return 0 if result["gateway_reachable"] and hops else 1


if __name__ == "__main__":
    sys.exit(main())
