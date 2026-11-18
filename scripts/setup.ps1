# Internet Health Monitor - Development Setup (PowerShell wrapper)
# This script wraps the Python setup script for Windows users.

$ErrorActionPreference = "Stop"

# Find Python
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} else {
    Write-Host "Error: Python not found. Please install Python 3.12+." -ForegroundColor Red
    exit 1
}

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Run the Python setup script
& $pythonCmd "$scriptDir\setup.py"
