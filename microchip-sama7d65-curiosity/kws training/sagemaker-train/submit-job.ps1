[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ImageUri,

    [Parameter(Mandatory = $true)]
    [string]$RoleArn,

    [Parameter(Mandatory = $true)]
    [string]$DatasetS3Uri,

    [Parameter(Mandatory = $true)]
    [string]$OutputBucket,

    [string]$ManifestS3Uri = "",
    [string]$Region = $(if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }),
    [string]$OutputPrefix = "kws-training/output",
    [string]$WeightsPrefix = "kws-training/weights",
    [string]$InstanceType = "ml.m5.xlarge",
    [int]$Epochs = 20,
    [int]$BatchSize = 16,
    [double]$LearningRate = 0.001,
    [string]$WantedWords = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$pythonExe = Join-Path $PSScriptRoot ".venv-tools\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Tooling venv is missing. Run .\setup-powershell.ps1 first."
}

$argsList = @(
    (Join-Path $PSScriptRoot "submit_job.py"),
    "--region", $Region,
    "--role-arn", $RoleArn,
    "--image-uri", $ImageUri,
    "--dataset-s3-uri", $DatasetS3Uri,
    "--output-bucket", $OutputBucket,
    "--output-prefix", $OutputPrefix,
    "--weights-prefix", $WeightsPrefix,
    "--instance-type", $InstanceType,
    "--epochs", $Epochs,
    "--batch-size", $BatchSize,
    "--learning-rate", $LearningRate
)

if ($ManifestS3Uri) {
    $argsList += @("--manifest-s3-uri", $ManifestS3Uri)
}
if ($WantedWords) {
    $argsList += @("--wanted-words", $WantedWords)
}
if ($DryRun) {
    $argsList += "--dry-run"
}

& $pythonExe @argsList
