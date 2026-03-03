param(
  [Parameter(Mandatory = $true)]
  [string]$ReferenceDesignRoot,
  [string]$RepoZipUrl = "https://github.com/avnet-iotconnect/iotc-python-lite-sdk-demos/archive/refs/heads/polarfire-workshop.zip",
  [string]$LocalModulePath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$tempRoot = Join-Path $env:TEMP ("iotc-mlnn-" + [guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $tempRoot "repo.zip"
$extractDir = Join-Path $tempRoot "extract"

try {
  $moduleSource = ""

  if ($LocalModulePath -and $LocalModulePath.Trim().Length -gt 0) {
    $moduleSource = (Resolve-Path $LocalModulePath).Path
    if (-not (Test-Path $moduleSource)) {
      throw "Local module path not found: $LocalModulePath"
    }
    Write-Host "Using local module path: $moduleSource"
  } else {
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    New-Item -ItemType Directory -Force -Path $extractDir | Out-Null

    Write-Host "Downloading workshop repo zip..."
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
      & curl.exe -L --retry 3 --retry-delay 2 --output $zipPath $RepoZipUrl | Out-Null
    } else {
      Invoke-WebRequest -Uri $RepoZipUrl -OutFile $zipPath -MaximumRedirection 10
    }

    if (-not (Test-Path $zipPath)) {
      throw "Download failed: $zipPath not found"
    }

    $zipHeader = [System.IO.File]::ReadAllBytes($zipPath)
    if ($zipHeader.Length -lt 2 -or $zipHeader[0] -ne 0x50 -or $zipHeader[1] -ne 0x4B) {
      throw "Downloaded file is not a valid ZIP (PK) archive: $zipPath"
    }

    Write-Host "Extracting zip..."
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

    $repoRoot = Get-ChildItem -Path $extractDir -Directory | Select-Object -First 1
    if (-not $repoRoot) {
      throw "Unable to find extracted repository root under $extractDir"
    }

    $moduleSource = Join-Path $repoRoot.FullName "microchip-polarfire-soc-dk\ml-simple-nn-accelerator\assets\smarthls-module\tinyml_nn"
    if (-not (Test-Path $moduleSource)) {
      $legacyModuleSource = Join-Path $repoRoot.FullName "microchip-polarfire-soc-dk\ml-simple-nn-accelerator\assets\smarthls-module\tinyml_nn"
      if (Test-Path $legacyModuleSource) {
        $moduleSource = $legacyModuleSource
      } else {
        throw "tinyml_nn module not found in downloaded repo. Checked: $moduleSource and $legacyModuleSource. Use a branch/tag that contains microchip-polarfire-soc-dk/ml-simple-nn-accelerator/assets/smarthls-module/tinyml_nn, or pass -LocalModulePath."
      }
    }
  }

  $moduleDest = Join-Path $ReferenceDesignRoot "script_support\additional_configurations\smarthls\tinyml_nn"
  New-Item -ItemType Directory -Force -Path (Split-Path $moduleDest -Parent) | Out-Null

  if (Test-Path $moduleDest) {
    Remove-Item -Recurse -Force $moduleDest
  }

  Write-Host "Copying tinyml_nn module into reference design..."
  Copy-Item -Recurse -Force $moduleSource $moduleDest

  Write-Host "Done."
  Write-Host "Module installed at: $moduleDest"
}
finally {
  if (Test-Path $tempRoot) {
    Remove-Item -Recurse -Force $tempRoot
  }
}
