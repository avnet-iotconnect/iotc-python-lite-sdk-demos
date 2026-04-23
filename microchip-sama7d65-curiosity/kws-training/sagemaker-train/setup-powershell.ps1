[CmdletBinding()]
param(
    [string]$PythonCommand = "py -3"
)

$ErrorActionPreference = "Stop"

Write-Host "Checking local tools..."
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "AWS CLI v2 is required. Install it, then rerun this script."
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required. Install it, then rerun this script."
}

$venvPath = Join-Path $PSScriptRoot ".venv-tools"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "Creating tooling virtual environment at $venvPath"
    Invoke-Expression "$PythonCommand -m venv `"$venvPath`""
}

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $PSScriptRoot "tooling-requirements.txt")

Write-Host ""
Write-Host "PowerShell is the recommended Windows workflow for this SageMaker trainer."
Write-Host "Use this in each new shell if script execution is blocked:"
Write-Host "  Set-ExecutionPolicy -Scope Process Bypass"
Write-Host ""
Write-Host "Tooling ready."
Write-Host "Python helper: $pythonExe"
