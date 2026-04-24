[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AccountId,

    [string]$Region = $(if ($env:AWS_REGION) { $env:AWS_REGION } else { "us-east-1" }),

    [string]$RepositoryName = "kws-training-trainer",

    [string]$ImageTag = $(Get-Date -Format "yyyyMMdd-HHmmss"),

    [string]$Platform = "linux/amd64"
)

$ErrorActionPreference = "Stop"

$repoUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/$RepositoryName"
$imageUri = "${repoUri}:${ImageTag}"

Write-Host "Ensuring ECR repository exists: $RepositoryName"
cmd /c "aws ecr describe-repositories --region $Region --repository-names $RepositoryName >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
    & aws ecr create-repository --region $Region --repository-name $RepositoryName | Out-Null
}

Write-Host "Logging Docker into ECR"
& aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"

Write-Host "Building image $imageUri"
docker build --platform $Platform -t $imageUri $PSScriptRoot

Write-Host "Pushing image $imageUri"
docker push $imageUri

Write-Host ""
Write-Host "Image URI:"
Write-Output $imageUri
