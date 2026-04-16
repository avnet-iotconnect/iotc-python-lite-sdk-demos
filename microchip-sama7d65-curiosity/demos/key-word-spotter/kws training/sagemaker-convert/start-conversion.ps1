[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProcessingImageUri,

    [Parameter(Mandatory = $true)]
    [string]$InputS3Uri,

    [Parameter(Mandatory = $true)]
    [string]$OutputS3Uri,

    [Parameter(Mandatory = $true)]
    [string]$StateMachineArn,
    [string]$WeightsName = "model-state.pt",
    [string]$ProjectName = "kws-training",
    [string]$Region = $(if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }),
    [string]$InstanceType = "ml.m5.xlarge",
    [int]$VolumeSizeGb = 30,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$pythonExe = Join-Path $PSScriptRoot ".venv-tools\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Tooling venv is missing. Run .\setup-powershell.ps1 first."
}

$argsList = @(
    (Join-Path $PSScriptRoot "start_execution.py"),
    "--region", $Region,
    "--state-machine-arn", $StateMachineArn,
    "--processing-image-uri", $ProcessingImageUri,
    "--input-s3-uri", $InputS3Uri,
    "--weights-name", $WeightsName,
    "--output-s3-uri", $OutputS3Uri,
    "--project-name", $ProjectName,
    "--instance-type", $InstanceType,
    "--volume-size-gb", $VolumeSizeGb
)

if ($DryRun) {
    $argsList += "--dry-run"
}

& $pythonExe @argsList
