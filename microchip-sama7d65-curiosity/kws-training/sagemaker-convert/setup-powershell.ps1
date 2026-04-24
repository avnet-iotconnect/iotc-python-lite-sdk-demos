[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "Checking local tools..."
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "AWS CLI v2 is required. Install it, then rerun this script."
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required. Install it, then rerun this script."
}
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' is required on Windows."
}

$venvPath = Join-Path $PSScriptRoot ".venv-tools"
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating tooling virtual environment at $venvPath"
    & py -3 -m venv $venvPath
}

$pythonExe = Join-Path $venvPath "Scripts\python.exe"
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $PSScriptRoot "tooling-requirements.txt")

Write-Host ""
Write-Host "PowerShell is the recommended Windows workflow for this SageMaker converter."
Write-Host "Use this in each new shell if script execution is blocked:"
Write-Host "  Set-ExecutionPolicy -Scope Process Bypass"
Write-Host ""
Write-Host "Tooling ready."
Write-Host "Python helper: $pythonExe"
