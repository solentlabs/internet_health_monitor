#!/usr/bin/env python3
# Internet Health Monitor - Automated Development Environment Setup (Python)
# This script consolidates the setup logic for all platforms.

import os
import platform
import re
import shutil
import subprocess
import sys

# ========================================
# Color Codes
# ========================================
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"


# ========================================
# Helper Functions
# ========================================
def print_step(message):
    print(f"{CYAN}➜{NC} {message}")


def print_success(message):
    print(f"{GREEN}✓{NC} {message}")


def print_error(message):
    print(f"{RED}✗{NC} {message}", file=sys.stderr)


def print_warning(message):
    print(f"{YELLOW}⚠{NC} {message}")


def run_command(command, quiet=False):
    """Runs a command and returns its output."""
    try:
        process = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
        )
        if not quiet:
            print(process.stdout)
        return process.stdout.strip()
    except subprocess.CalledProcessError as e:
        if not quiet:
            print_error(f"Command failed: {command}")
            print(e.stderr, file=sys.stderr)
        raise


def get_required_python_version():
    """Parse pyproject.toml to get the required Python version."""
    if not os.path.exists("pyproject.toml"):
        return (3, 12)  # Default fallback

    with open("pyproject.toml") as f:
        content = f.read()

    # Match requires-python = ">=3.12" or ">=3.12,<3.13" etc.
    match = re.search(r'requires-python\s*=\s*">=(\d+)\.(\d+)', content)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return (3, 12)  # Default fallback


def get_debian_version():
    """Get Debian/Ubuntu version info if applicable."""
    try:
        with open("/etc/os-release") as f:
            content = f.read()
        version_match = re.search(r"VERSION_CODENAME=(\w+)", content)
        id_match = re.search(r"^ID=(\w+)", content, re.MULTILINE)
        if version_match and id_match:
            return (id_match.group(1), version_match.group(1))
    except FileNotFoundError:
        pass
    return (None, None)


def print_python_install_instructions(required_major, required_minor):
    """Print platform-specific Python installation instructions."""
    distro, codename = get_debian_version()
    is_chromeos = os.path.exists("/dev/.cros_milestone") or "chromeos" in platform.platform().lower()

    print("")
    print(f"  Python {required_major}.{required_minor} is required but not installed.")
    print("")

    if distro == "debian" and codename == "bookworm":
        print("  Debian 12 (bookworm) ships with Python 3.11. To install Python 3.12:")
        print("")
        print("  Option 1: Use pyenv (recommended)")
        print("    curl https://pyenv.run | bash")
        print("    # Follow the instructions to add pyenv to your shell")
        print("    pyenv install 3.12")
        print("    pyenv local 3.12")
        print("")
        if is_chromeos:
            print("  Note: Chrome OS Flex uses Debian bookworm in Crostini.")
            print("  pyenv works well in this environment.")
            print("")
    elif distro == "ubuntu":
        print("  Ubuntu - install from deadsnakes PPA:")
        print("")
        print("    sudo apt install software-properties-common")
        print("    sudo add-apt-repository ppa:deadsnakes/ppa")
        print("    sudo apt update")
        py_ver = f"{required_major}.{required_minor}"
        print(f"    sudo apt install python{py_ver} python{py_ver}-venv")
        print("")
    elif platform.system() == "Darwin":
        print("  macOS - install with Homebrew:")
        print("")
        print(f"    brew install python@{required_major}.{required_minor}")
        print("")
    elif platform.system() == "Windows":
        print("  Windows - download from python.org:")
        print("")
        print(f"    https://www.python.org/downloads/release/python-{required_major}{required_minor}0/")
        print("")
    else:
        print("  Install Python 3.12 using your system's package manager or pyenv:")
        print("")
        print("    curl https://pyenv.run | bash")
        print("    pyenv install 3.12")
        print("")


# ========================================
# Main Setup Logic
# ========================================
def main():  # noqa: C901
    print("")
    print("==========================================")
    print("Internet Health Monitor - Development Setup")
    print("==========================================")
    print("")

    # 1. Check if in project root
    print_step("Checking if in project root directory...")
    if not os.path.exists("custom_components/internet_health_monitor/__init__.py"):
        print_error("Not in project root directory")
        print("\nPlease run this script from the internet_health_monitor/ directory:")
        print("  cd /path/to/internet_health_monitor")
        print("  python3 scripts/setup.py\n")
        sys.exit(1)
    print_success("Running from project root")
    print("")

    # 2. Check Python version against pyproject.toml requirement
    print_step("Checking Python version...")
    current_major, current_minor = sys.version_info[:2]
    required_major, required_minor = get_required_python_version()

    if current_major == required_major and current_minor >= required_minor:
        print_success(f"Python {current_major}.{current_minor} found (requirement: {required_major}.{required_minor}+)")
    else:
        print_error(f"Python {current_major}.{current_minor} found, but {required_major}.{required_minor}+ required")
        print_python_install_instructions(required_major, required_minor)
        sys.exit(1)
    print("")

    # 3. Check for venv module
    print_step("Checking for venv module...")
    import importlib.util

    if importlib.util.find_spec("venv") is not None:
        print_success("venv module available")
    else:
        print_error("venv module not installed")
        print("\nInstall it with:")
        print(f"  Linux/macOS: sudo apt install python{current_major}.{current_minor}-venv")
        print("  Windows: venv is included with Python\n")
        sys.exit(1)
    print("")

    # 4. Clean up old venv
    if os.path.isdir("venv"):
        print_warning("Found venv/ directory, removing it in favor of .venv/")
        shutil.rmtree("venv")
        print_success("Removed venv/ directory")
        print("")

    # 5. Create virtual environment
    is_windows = platform.system() == "Windows"
    pip_cmd = os.path.join(".venv", "Scripts", "pip.exe") if is_windows else os.path.join(".venv", "bin", "pip")
    python_cmd = (
        os.path.join(".venv", "Scripts", "python.exe") if is_windows else os.path.join(".venv", "bin", "python")
    )

    print_step("Creating virtual environment...")
    if os.path.exists(".venv") and os.path.exists(pip_cmd):
        print_success("Virtual environment already exists")
    elif os.path.exists(".venv"):
        print_warning("Virtual environment is incomplete, recreating...")
        try:
            shutil.rmtree(".venv")
            print_success("Removed incomplete venv")
        except OSError:
            print_error("Cannot remove .venv (files are locked)")
            print("")
            print("This happens when VS Code or another process is using the venv.")
            print("")
            print("Solutions:")
            if is_windows:
                print("  1. Close ALL VS Code windows")
                print("  2. Open PowerShell/Command Prompt (NOT VS Code)")
                print("  3. Run: Remove-Item -Recurse -Force .venv")
                print("  4. Run this setup again")
            else:
                print("  1. Close VS Code")
                print("  2. Run: rm -rf .venv")
                print("  3. Run this setup again")
            print("")
            sys.exit(1)
        run_command(f"{sys.executable} -m venv .venv")
        print_success("Virtual environment created")
    else:
        run_command(f"{sys.executable} -m venv .venv")
        print_success("Virtual environment created")
    print("")

    # 6. Upgrade pip
    print_step("Upgrading pip...")
    try:
        run_command(f"{pip_cmd} install --upgrade pip", quiet=True)
        print_success("pip ready")
    except Exception:
        print_warning("pip upgrade skipped (will work next run)")
    print("")

    # 7. Install dependencies
    print_step("Installing development dependencies...")
    print("  (This may take a few minutes...)")
    if os.path.exists("requirements-dev.txt"):
        run_command(f"{pip_cmd} install --quiet -r requirements-dev.txt")
        print_success("Development dependencies installed from requirements-dev.txt")
    else:
        print_warning("requirements-dev.txt not found, using fallback installation")
        # Install packages manually
        packages = [
            "homeassistant>=2025.1.0",
            "pytest",
            "pytest-cov",
            "pytest-asyncio",
            "pytest-mock",
            "ruff",
            "black",
        ]
        # Quote each spec: unquoted, the shell reads ">=" as a redirect and
        # creates a file named "=<version>" in the repo root.
        quoted = " ".join('"' + p + '"' for p in packages)
        run_command(f"{pip_cmd} install --quiet {quoted}")
        print_success("Development dependencies installed")
    print("")

    # 8. Check Docker
    print_step("Checking Docker...")
    if shutil.which("docker"):
        try:
            docker_version = run_command("docker --version", quiet=True).split(" ")[2].strip(",")
            run_command("docker ps", quiet=True)
            print_success(f"Docker {docker_version} is running")
        except Exception:
            print_warning("Docker installed but not running")
            print("  Start Docker Desktop to use dev containers")
    else:
        print_warning("Docker not installed")
        print("  Optional: Install Docker Desktop for containerized development")
    print("")

    # 9. Run a quick test
    print_step("Running quick test to verify setup...")
    try:
        run_command(f"{python_cmd} -m pytest tests/core/test_network_diagnostics.py -q --tb=short", quiet=True)
        print_success("Tests can run successfully")
    except Exception:
        print_warning("Test execution had issues (may need additional setup)")
    print("")

    # Final message
    print("==========================================")
    print("Setup Complete!")
    print("==========================================")
    print("")
    print(f"{GREEN}✓ Your development environment is ready!{NC}")
    print("")
    print("What's installed:")
    print("  • Python virtual environment (.venv/)")
    print("  • All development dependencies")
    print("  • Code formatters and linters")
    print("")
    print("Next steps:")
    print("")
    print(f"  {CYAN}1. Run tests:{NC}")
    print("     pytest")
    print("")
    print(f"  {CYAN}2. Run code quality checks:{NC}")
    print("     ruff check .")
    print("     black .")
    print("")
    print(f"  {CYAN}3. Open in VS Code:{NC}")
    print("     code .")
    print("")
    print("Happy coding! 🚀")
    print("")


if __name__ == "__main__":
    main()
