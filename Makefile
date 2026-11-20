.PHONY: help pyright markdownlint spell-check hassfest setup-current test-current test-all test-windows coverage-gates test test-quick clean lint lint-fix type-check format format-check check setup

# Default target - show help
help:
	@echo "Internet Health Monitor - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup         - .venv: oldest supported HA (ha-minimum.txt), Python 3.14"
	@echo "  make setup-current - .venv-current: newest HA the test harness supports"
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
	@echo "  make pyright     - Pyright as VS Code runs it (pyrightconfig.json; needs Node.js; same as CI)"
	@echo "  make markdownlint - Markdown rules as VS Code runs them (.markdownlint.jsonc; needs Node.js)"
	@echo "  make format      - Format code with black"
	@echo "  make format-check - Check code formatting without modifying"
	@echo "  make spell-check - cspell over the repo (needs Node.js; same as CI)"
	@echo "  make hassfest    - HA's integration validator (Docker; same image as CI)"
	@echo "  make check       - Run all code quality checks (lint, format, mypy, pyright, Markdown, spelling)"

# Setup development environment
setup:
	@echo "Creating virtual environment..."
	uv venv --allow-existing --seed --python 3.14 .venv
	@echo "Installing dependencies..."
	uv pip install --python .venv -r requirements-dev.txt -c ha-minimum.txt
	@echo "Installing pre-commit hooks..."
	.venv/bin/pre-commit install
	@echo "Setup complete! Activate with: source .venv/bin/activate"

# Newest HA the test harness supports
setup-current:
	uv venv --allow-existing --python 3.14 .venv-current
	uv pip install --python .venv-current -r requirements-dev.txt

# Run full test suite with coverage (minimum HA), then the coverage gates
test:
	@.venv/bin/pytest
	@$(MAKE) --no-print-directory coverage-gates

# HA layer above 95%, the quality scale's test-coverage threshold; Core 90%
coverage-gates:
	@.venv/bin/coverage report --include="custom_components/*" --fail-under=95 > /dev/null && echo "HA layer coverage >= 95%"
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
	@.venv/bin/mypy
	@.venv-current/bin/mypy

# Pyright, as VS Code's Pylance runs it (pyrightconfig.json), on both HA versions. Same as CI.
PYRIGHT := npx --yes pyright@1.1.414
pyright:
	@echo "Running pyright..."
	@$(PYRIGHT) --pythonpath .venv/bin/python
	@$(PYRIGHT) --pythonpath .venv-current/bin/python

# Format code
format:
	@echo "Formatting code with Black..."
	@.venv/bin/black .

# Check code formatting without modifying
format-check:
	@echo "Checking code formatting..."
	@.venv/bin/black --check .

# Run all code quality checks
# Spelling: cspell.config.yaml holds the project dictionary. Same command as CI.
# Markdown, as VS Code's markdownlint extension runs it (.markdownlint.jsonc). Same as CI.
markdownlint:
	@echo "Running markdownlint..."
	@git ls-files '*.md' | xargs npx --yes markdownlint-cli2@0.24.1

spell-check:
	@npx --yes cspell@10 --config cspell.config.yaml --gitignore --dot --no-progress "**/*.{py,md,yaml,yml,json,toml,sh,txt}"

# HA's own validator: manifest, translations, quality_scale.yaml. Same image as CI.
hassfest:
	@docker run --rm -v "$(CURDIR)://github/workspace" ghcr.io/home-assistant/hassfest

check: lint format-check type-check pyright markdownlint spell-check
	@echo "All code quality checks passed!"
