# VS Code terminal auto-activation script for PowerShell
# This runs automatically when you open a terminal in VS Code

$VenvPath = ".venv"
$ActivateScript = "$VenvPath\Scripts\Activate.ps1"

if (Test-Path $ActivateScript) {
    # .venv exists, activate it and show "next steps" message
    & $ActivateScript
    Clear-Host
    Write-Host ""
    Get-Content "$PSScriptRoot\next_steps.txt"
    Write-Host ""
} else {
    # .venv doesn't exist or isn't set up - show helpful instructions
    Get-Content "$PSScriptRoot\welcome_message.txt"
    Write-Host ""
}
