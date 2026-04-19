# Build Tezis.exe from ui_flet/main.py via `flet pack`.
#
# Output: dist/Tezis.exe (+ _internal/ for onedir mode)
#
# Bundled resources:
#   - seed DB at data/state_exam_public_admin_demo.db
#   - assets/icon.ico (if present)
#   - TTF fonts if ui_flet/theme/fonts/*.ttf are dropped in advance
#
# Takes 10-20 minutes on a fresh machine (pyinstaller re-bundles Flet,
# Qt libs, cpython, and all dependencies). Expect ~150-250 MB output.
#
# Usage:
#   .\scripts\build_flet_exe.cmd                   # recommended on Windows
#   powershell -ExecutionPolicy Bypass -File .\scripts\build_flet_exe.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\build_flet_exe.ps1 -OutputDir build\dist

param(
  [string]$OutputDir = "dist",
  [string]$IconPath = "assets\icon.ico",
  [switch]$SkipSeedCheck
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

function Resolve-BuilderPath {
  param([Parameter(Mandatory = $true)][string]$PathValue)

  if ([System.IO.Path]::IsPathRooted($PathValue)) {
    return [System.IO.Path]::GetFullPath($PathValue)
  }

  return [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $PathValue))
}

function Stop-TezisProcessesForPath {
  param([Parameter(Mandatory = $true)][string]$ExePath)

  $fullExePath = [System.IO.Path]::GetFullPath($ExePath)
  $matching = @(
    Get-Process -Name "Tezis" -ErrorAction SilentlyContinue | Where-Object {
      try {
        $_.Path -and [System.IO.Path]::GetFullPath($_.Path).Equals($fullExePath, [System.StringComparison]::OrdinalIgnoreCase)
      } catch {
        $false
      }
    }
  )

  if ($matching.Count -gt 0) {
    Write-Host "Stopping running Tezis.exe before rebuild..." -ForegroundColor Yellow
    $matching | Stop-Process -Force
    Start-Sleep -Milliseconds 800
  }
}

function Remove-BuilderPath {
  param(
    [Parameter(Mandatory = $true)][string]$PathValue,
    [Parameter(Mandatory = $true)][string]$Label
  )

  if (-not (Test-Path -LiteralPath $PathValue)) {
    return
  }

  for ($attempt = 1; $attempt -le 5; $attempt++) {
    try {
      Remove-Item -LiteralPath $PathValue -Recurse -Force -ErrorAction Stop
      return
    } catch {
      if ($attempt -eq 1 -and $PathValue.EndsWith(".exe", [System.StringComparison]::OrdinalIgnoreCase)) {
        Stop-TezisProcessesForPath -ExePath $PathValue
      }
      if ($attempt -eq 5) {
        throw "Failed to remove $Label at $PathValue. $($_.Exception.Message)"
      }
      Start-Sleep -Milliseconds (400 * $attempt)
    }
  }
}

# ---- sanity ----
$seedDb = Join-Path $ProjectRoot "data\state_exam_public_admin_demo.db"
if (-not $SkipSeedCheck -and -not (Test-Path $seedDb)) {
  Write-Error "Seed DB missing at $seedDb - copy from data-pipeline worktree build/demo_seed/ first"
}

$entryPoint = Join-Path $ProjectRoot "ui_flet\main.py"
if (-not (Test-Path $entryPoint)) {
  Write-Error "Entry point not found: $entryPoint"
}

$resolvedOutputDir = Resolve-BuilderPath -PathValue $OutputDir
$stagingOutputDir = Join-Path $ProjectRoot ("build\flet-pack-stage-" + [guid]::NewGuid().ToString("N"))
$stagingExePath = Join-Path $stagingOutputDir "Tezis.exe"
$finalExePath = Join-Path $resolvedOutputDir "Tezis.exe"

$iconArgs = @()
$fullIconPath = Join-Path $ProjectRoot $IconPath
if (Test-Path $fullIconPath) {
  $iconArgs = @("--icon", $IconPath)
} else {
  Write-Warning "Icon not found at $IconPath — build will use Flet default icon"
}

# ---- add-data entries ----
# Format on Windows is "<src>;<dest>". Flet pack relays these to PyInstaller.
$addData = @()
if (Test-Path $seedDb) {
  $addData += @("--add-data", "data\state_exam_public_admin_demo.db;data")
}
$fontsDir = Join-Path $ProjectRoot "ui_flet\theme\fonts"
if ((Test-Path $fontsDir) -and (Get-ChildItem $fontsDir -Filter "*.ttf" -ErrorAction SilentlyContinue)) {
  $addData += @("--add-data", "ui_flet\theme\fonts\*.ttf;ui_flet\theme\fonts")
}

# ---- dispatch ----
Write-Host "=== Building Tezis.exe via flet pack ===" -ForegroundColor Cyan
Write-Host "  entry point   : $entryPoint"
Write-Host "  output dir    : $resolvedOutputDir"
Write-Host "  icon          : $(if ($iconArgs.Count) { $iconArgs[1] } else { '(default)' })"
Write-Host "  add-data      : $(if ($addData.Count) { ($addData -join ' ') } else { '(none)' })"
Write-Host ""

$args = @(
  "pack", "ui_flet\main.py",
  "--name", "Tezis",
  "--distpath", $stagingOutputDir,
  "--product-name", "Тезис",
  "--file-description", "Подготовка к письменному госэкзамену ГМУ",
  "--company-name", "ВШГА МГУ",
  "--yes"
) + $iconArgs + $addData

try {
  Remove-BuilderPath -PathValue $stagingOutputDir -Label "staging dist"

  & flet @args
  if ($LASTEXITCODE -ne 0) {
    Write-Error "flet pack failed with exit code $LASTEXITCODE"
  }

  if (-not (Test-Path -LiteralPath $stagingExePath)) {
    Write-Error "Build finished but staged exe is missing at $stagingExePath"
  }

  New-Item -ItemType Directory -Force -Path $resolvedOutputDir | Out-Null
  Remove-BuilderPath -PathValue $finalExePath -Label "previous dist exe"
  Copy-Item -LiteralPath $stagingExePath -Destination $finalExePath -Force

  $sizeMb = [math]::Round((Get-Item $finalExePath).Length / 1MB, 1)
  Write-Host ""
  Write-Host ("+ Built: {0} ({1} MB)" -f $finalExePath, $sizeMb) -ForegroundColor Green
  exit 0
} finally {
  if (Test-Path -LiteralPath $stagingOutputDir) {
    try {
      Remove-Item -LiteralPath $stagingOutputDir -Recurse -Force -ErrorAction Stop
    } catch {
      Write-Warning "Could not remove staging dir $stagingOutputDir"
    }
  }
}
