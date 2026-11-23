#!/usr/bin/env python3
"""Cross-platform pre-commit validation script.

Works on Linux, macOS, and Windows without requiring a venv.
Auto-installs missing tools (ruff, black) if needed.

Usage:
    python scripts/dev/validate.py              # Run all checks
    python scripts/dev/validate.py --lint       # Lint only
    python scripts/dev/validate.py --format     # Format check only
"""

import argparse
import subprocess
import sys


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def tool_exists(name: str) -> bool:
    """Check if a tool is available via python -m."""
    try:
        result = run_command([sys.executable, "-m", name, "--version"], check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_tool(package: str) -> bool:
    """Install a Python package using pip."""
    print(f"  Installing {package}...")
    try:
        result = run_command(
            [sys.executable, "-m", "pip", "install", package, "--quiet"],
            check=False,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  Failed to install {package}: {e}")
        return False


def ensure_tool(name: str, package: str | None = None) -> bool:
    """Ensure a tool is available, installing if necessary."""
    if tool_exists(name):
        return True

    pkg = package or name
    print(f"⚠️  {name} not found, installing...")

    if install_tool(pkg):
        if tool_exists(name):
            print(f"  ✓ {name} installed successfully")
            return True
        else:
            print(f"  ✓ {name} installed (will use via python -m)")
            return True

    print(f"  ✗ Failed to install {name}")
    return False


def run_tool(name: str, args: list[str]) -> tuple[int, str, str]:
    """Run a tool via python -m (most reliable cross-platform)."""
    result = run_command([sys.executable, "-m", name] + args, check=False)
    return result.returncode, result.stdout, result.stderr


def check_lint() -> bool:
    """Run ruff linter."""
    print("🔍 Running ruff linter...")

    if not ensure_tool("ruff"):
        return False

    returncode, stdout, stderr = run_tool("ruff", ["check", "."])

    if returncode != 0:
        print(stderr or stdout)
        print("  ✗ Linting failed")
        return False

    print("  ✓ Linting passed")
    return True


def check_format() -> bool:
    """Check black formatting."""
    print("🎨 Checking code formatting (black)...")

    if not ensure_tool("black"):
        return False

    returncode, stdout, stderr = run_tool("black", ["--check", "."])

    if returncode != 0:
        print(stderr or stdout)
        print("  ✗ Formatting check failed")
        print("  Run 'black .' to fix formatting")
        return False

    print("  ✓ Formatting check passed")
    return True


def main() -> int:
    """Run validation checks."""
    parser = argparse.ArgumentParser(description="Pre-commit validation")
    parser.add_argument("--lint", action="store_true", help="Run lint check only")
    parser.add_argument("--format", action="store_true", help="Run format check only")
    args = parser.parse_args()

    # With neither flag, run both.
    results = []

    if args.lint or not args.format:
        results.append(("Lint", check_lint()))

    if args.format or not args.lint:
        results.append(("Format", check_format()))

    print("")
    failed = [name for name, passed in results if not passed]

    if failed:
        print(f"❌ Validation failed: {', '.join(failed)}")
        return 1

    print("✅ All checks passed - ready to commit!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
