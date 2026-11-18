#!/bin/bash
# This script is a thin wrapper that executes the main Python setup script.

# Exit on error
set -e

# Initialize pyenv if available (for Python version management)
if [ -d "$HOME/.pyenv" ]; then
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
fi

# Find a suitable Python interpreter
# Try specific pyenv version first, then python3, then python
if [ -n "$PYENV_ROOT" ] && [ -x "$PYENV_ROOT/versions/3.12.12/bin/python" ]; then
    PYTHON_CMD="$PYENV_ROOT/versions/3.12.12/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3.12+."
    exit 1
fi

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Execute the main Python setup script
$PYTHON_CMD "$SCRIPT_DIR/setup.py"
