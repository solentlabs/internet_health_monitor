.PHONY: help test test-quick clean lint lint-fix type-check format format-check check setup

# Default target - show help
help:
	@echo "HA Network Diagnostics - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup       - Create venv and install dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test        - Run full test suite with coverage"
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
	python3 -m venv .venv
	@echo "Installing dependencies..."
	.venv/bin/pip install -e ".[dev]"
	@echo "Installing pre-commit hooks..."
	.venv/bin/pre-commit install
	@echo "Setup complete! Activate with: source .venv/bin/activate"

# Run full test suite with coverage
test:
	@.venv/bin/pytest --cov=custom_components/internet_health_monitor --cov-report=term-missing

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
	@.venv/bin/mypy --explicit-package-bases custom_components/internet_health_monitor

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
