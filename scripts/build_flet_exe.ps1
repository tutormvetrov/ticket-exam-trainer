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
#   .\scripts\build_flet_exe.ps1                   # default: dist/
#   .\scripts\build_flet_exe.ps1 -OutputDir build\dist

param(
  [string]$OutputDir = "dist",
  [string]$IconPath = "assets\icon.ico",
  [switch]$SkipSeedCheck
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

# ---- sanity ----
$seedDb = Join-Path $ProjectRoot "data\state_exam_public_admin_demo.db"
if (-not $SkipSeedCheck -and -not (Test-Path $seedDb)) {
  Write-Error "Seed DB missing at $seedDb - copy from data-pipeline worktree build/demo_seed/ first"
}

$entryPoint = Join-Path $ProjectRoot "ui_flet\main.py"
if (-not (Test-Path $entryPoint)) {
  Write-Error "Entry point not found: $entryPoint"
}

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
Write-Host "  output dir    : $OutputDir"
Write-Host "  icon          : $(if ($iconArgs.Count) { $iconArgs[1] } else { '(default)' })"
Write-Host "  add-data      : $(if ($addData.Count) { ($addData -join ' ') } else { '(none)' })"
Write-Host ""

$args = @(
  "pack", "ui_flet\main.py",
  "--name", "Tezis",
  "--distpath", $OutputDir,
  "--product-name", "Тезис",
  "--file-description", "Подготовка к письменному госэкзамену ГМУ",
  "--company-name", "ВШГА МГУ",
  "--yes"
) + $iconArgs + $addData

& flet @args
if ($LASTEXITCODE -ne 0) {
  Write-Error "flet pack failed with exit code $LASTEXITCODE"
}

$exePath = Join-Path $OutputDir "Tezis.exe"
if (Test-Path $exePath) {
  $sizeMb = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
  Write-Host ""
  Write-Host ("+ Built: {0} ({1} MB)" -f $exePath, $sizeMb) -ForegroundColor Green
  exit 0
} else {
  Write-Warning "Build finished but $exePath is missing. Check console output above."
  exit 1
}
