# ApexEngine Windows PowerShell Installer
$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "          Installing ApexEngine v2.1.0            " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Error "Python 3 is required to install ApexEngine."
    exit 1
}

$antigravityPath = "$env:USERPROFILE\.gemini\config\skills"
$targetDir = ""

if (Test-Path "$antigravityPath") {
    $targetDir = "$antigravityPath\apex-engine"
    Write-Host "Detected Google Antigravity environment: $targetDir" -ForegroundColor Green
} else {
    $targetDir = "$env:USERPROFILE\.apex-engine"
    Write-Host "Installing to user home: $targetDir" -ForegroundColor Green
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

$scriptDir = $PSScriptRoot
Copy-Item -Path "$scriptDir\SKILL.md" -Destination "$targetDir\" -Force
Copy-Item -Path "$scriptDir\scripts" -Destination "$targetDir\" -Recurse -Force
Copy-Item -Path "$scriptDir\templates" -Destination "$targetDir\" -Recurse -Force

Write-Host "ApexEngine successfully installed to $targetDir" -ForegroundColor Green
Write-Host "Run 'python `"$targetDir\scripts\condense.py`" init' in any repository to begin." -ForegroundColor Yellow
