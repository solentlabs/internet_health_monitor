#!/bin/bash
# Post-create setup for dev container
# This runs once when the container is first created

set -e

echo "📦 Installing Python dependencies..."
pip install --root-user-action=ignore -r requirements-dev.txt

echo "📦 Installing pre-commit..."
pip install --root-user-action=ignore pre-commit

echo "📦 Installing pre-commit hooks..."
pre-commit install --hook-type pre-commit --hook-type commit-msg || true

echo ""
echo "✅ Dev environment ready!"
echo ""
echo "📖 Quick Start:"
echo "  • Run tests: Ctrl+Shift+P → 'Tasks: Run Task' → 'Run All Tests'"
echo "  • View all tasks: Ctrl+Shift+P → 'Tasks: Run Task'"
echo ""
