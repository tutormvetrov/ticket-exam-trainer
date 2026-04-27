<#
.SYNOPSIS
    Собирает Tezis-Setup.exe локально. Требует уже собранный dist\Tezis.exe.
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
    throw "dist\Tezis.exe не найден. Сначала запусти scripts\build_flet_exe.ps1"
}

if (-not $Version) {
    $metaPath = Join-Path $repoRoot 'app\meta.py'
    $match    = Select-String -Path $metaPath -Pattern 'APP_VERSION\s*=\s*"([^"]+)"'
    $Version  = $match.Matches[0].Groups[1].Value
    if (-not $Version) { throw "Не удалось прочитать APP_VERSION из app\meta.py" }
}

Write-Host "Версия: $Version"

# Найти ISCC.exe
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidate = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
    if (Test-Path $candidate) { $iscc = $candidate }
    else { throw "ISCC.exe не найден. Установи: choco install innosetup" }
}

& $iscc "/DAppVersion=$Version" $iss
if ($LASTEXITCODE -ne 0) { throw "ISCC завершился с ошибкой $LASTEXITCODE" }

Write-Host "Готово -> dist\Tezis-Setup.exe"
