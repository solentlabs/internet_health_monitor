.PHONY: help setup-current test-current test-all test-windows coverage-gates test test-quick clean lint lint-fix type-check format format-check check setup

# Default target - show help
help:
	@echo "Internet Health Monitor - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup         - .venv on Python 3.12 via uv: minimum HA (2025.1.x)"
	@echo "  make setup-current - .venv-current on Python 3.14 via uv: newest HA"
	@echo ""
	@echo "Development:"
	@echo "  make test        - Tests with coverage on minimum HA (.venv)"
	@echo "  make test-current - Tests on newest HA (.venv-current)"
	@echo "  make test-all    - Both, plus coverage gates"
	@echo "  make test-windows - Run Core once on the Windows host's Python (WSL)"
	@echo "  make test-quick  - Quick test run (no coverage)"
	@echo "  make clean       - Remove test artifacts and cache files"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint        - Run ruff linter"
	@echo "  make lint-fix    - Run ruff linter and auto-fix issues"
	@echo "  make type-check  - Run mypy type checker"
	@echo "  make format      - Format code with black"
	@echo "  make format-check - Check code formatting without modifying"
	@echo "  make check       - Run all code quality checks (lint, format, type)"

# Setup development environment
setup:
	@echo "Creating virtual environment..."
	uv venv --allow-existing --seed --python 3.12 .venv
	@echo "Installing dependencies..."
	@# pip, not uv pip: HA 2025.1.x pins a pre-release (aiohasupervisor==0.2.2b5),
	@# which pip accepts and uv's resolver refuses.
	.venv/bin/pip install -r requirements-dev.txt
	@echo "Installing pre-commit hooks..."
	.venv/bin/pre-commit install
	@echo "Setup complete! Activate with: source .venv/bin/activate"

# Newest HA: needs Python 3.14 (uv installs it if missing)
setup-current:
	uv venv --allow-existing --python 3.14 .venv-current
	uv pip install --python .venv-current -r requirements-dev.txt

# Run full test suite with coverage (minimum HA), then the coverage gates
test:
	@.venv/bin/pytest
	@$(MAKE) --no-print-directory coverage-gates

# Same floors as Cable Modem Monitor: 70% HA layer, 90% Core
coverage-gates:
	@.venv/bin/coverage report --include="custom_components/*" --fail-under=70 > /dev/null && echo "HA layer coverage >= 70%"
	@.venv/bin/coverage report --include="*/solentlabs/internet_health_monitor_core/*" --fail-under=90 > /dev/null && echo "Core coverage >= 90%"

# Core on Windows for real, from WSL (sends a few pings; no speed test)
test-windows:
	@python3 scripts/dev/windows_check.py

# Tests on the newest HA
test-current:
	@.venv-current/bin/pytest -q

# Both HA versions
test-all: test test-current

# Quick test (no coverage)
test-quick:
	@.venv/bin/pytest -x -q

# Clean test artifacts
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__
	rm -rf .coverage htmlcov coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Run linter
lint:
	@echo "Running Ruff linter..."
	@.venv/bin/ruff check .

# Run linter with auto-fix
lint-fix:
	@echo "Running Ruff linter with auto-fix..."
	@.venv/bin/ruff check --fix .

# Type checking
type-check:
	@echo "Running mypy type checker..."
	@.venv/bin/mypy --explicit-package-bases custom_components/internet_health_monitor packages/internet_health_monitor_core/solentlabs

# Format code
format:
	@echo "Formatting code with Black..."
	@.venv/bin/black .

# Check code formatting without modifying
format-check:
	@echo "Checking code formatting..."
	@.venv/bin/black --check .

# Run all code quality checks
check: lint format-check type-check
	@echo "All code quality checks passed!"
