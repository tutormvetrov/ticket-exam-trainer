<#
.SYNOPSIS
    Builds Tezis-Setup.exe locally. Requires dist\Tezis.exe to be built first.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\installer\build_installer.ps1
    powershell -ExecutionPolicy Bypass -File scripts\installer\build_installer.ps1 -Version 2.5.3
#>
[CmdletBinding()]
param(
    [string]$Version = ''
)
$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$exe      = Join-Path $repoRoot 'dist\Tezis.exe'
$iss      = Join-Path $repoRoot 'scripts\installer\Tezis-Setup.iss'

if (-not (Test-Path -LiteralPath $exe)) {
    throw "dist\Tezis.exe not found. Run scripts\build_flet_exe.ps1 first."
}

if (-not $Version) {
    $metaPath = Join-Path $repoRoot 'app\meta.py'
    if (-not (Test-Path -LiteralPath $metaPath)) {
        throw "app\meta.py not found at: $metaPath"
    }
    $match = Select-String -Path $metaPath -Pattern 'APP_VERSION\s*=\s*"([^"]+)"'
    if (-not $match) { throw "Could not read APP_VERSION from app\meta.py" }
    $Version = $match.Matches[0].Groups[1].Value
}

if (-not (Test-Path -LiteralPath $iss)) {
    throw "Tezis-Setup.iss not found: $iss"
}

Write-Host "Version: $Version"

# Find ISCC.exe
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidate = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
    if (Test-Path -LiteralPath $candidate) { $iscc = $candidate }
    else { throw "ISCC.exe not found. Install with: choco install innosetup" }
}

& $iscc "/DAppVersion=$Version" $iss
if ($LASTEXITCODE -ne 0) { throw "ISCC failed with exit code $LASTEXITCODE" }

Write-Host "Done -> dist\Tezis-Setup.exe"
