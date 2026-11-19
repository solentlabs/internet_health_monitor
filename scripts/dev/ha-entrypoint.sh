#!/bin/bash
# Entrypoint for the HA dev container.
# Installs the local Core package before HA starts, so HA finds the version
# manifest.json pins without downloading it from PyPI.

set -e

CORE=/workspace/packages/internet_health_monitor_core

echo "=== Installing solentlabs packages ==="
if [ -d "$CORE" ]; then
    pip install --quiet -e "$CORE"
    echo "  Core installed"
else
    echo "  WARNING: Core package not found at $CORE"
fi

echo "=== Starting Home Assistant ==="
exec /init
