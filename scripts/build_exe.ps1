param(
    [string]$PythonExe = "python",
    [string]$SeedDatabasePath = "",
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $root "dist"
$buildRoot = Join-Path $root "build"
$releaseName = "Tezis"
$releaseDir = Join-Path $distRoot $releaseName
$releaseZip = Join-Path $distRoot "$releaseName-windows.zip"
$stageDistRoot = Join-Path $buildRoot "release_stage"
$stageReleaseDir = Join-Path $stageDistRoot $releaseName
$workDir = Join-Path $buildRoot "pyinstaller"
$specDir = Join-Path $buildRoot "spec"
$buildInfoPath = Join-Path $releaseDir "build_info.json"
$appVersion = (& $PythonExe -c "from app.meta import APP_VERSION; print(APP_VERSION)" | Select-Object -First 1).Trim()
$resolvedSeedDbPath = ""

if (-not $SeedDatabasePath) {
    $SeedDatabasePath = $env:TEZIS_SEED_DATABASE
}
if ($SeedDatabasePath) {
    $resolvedSeedDbPath = (
        & $PythonExe -c "from app.release_seed import resolve_seed_database; import sys; resolved = resolve_seed_database(sys.argv[1]); print(resolved if resolved is not None else '')" $SeedDatabasePath |
            Select-Object -First 1
    ).Trim()
}

Write-Host "Building release into $releaseDir"
Write-Host "Repo root is the source of truth; packaged README/docs/scripts will be regenerated from root."
if ($resolvedSeedDbPath) {
    Write-Host "Bundling explicit seed database: $resolvedSeedDbPath"
} else {
    Write-Host "No seed database requested; packaged app will create exam_trainer.db in the user workspace on first launch."
}

New-Item -ItemType Directory -Force -Path $distRoot | Out-Null

$runningReleaseProcesses = @(Get-Process -Name $releaseName -ErrorAction SilentlyContinue | Where-Object {
    try {
        $_.Path -and $_.Path.StartsWith($releaseDir, [System.StringComparison]::OrdinalIgnoreCase)
    } catch {
        $false
    }
})
if ($runningReleaseProcesses.Count -gt 0) {
    Write-Host "Stopping running packaged app before rebuild..."
    $runningReleaseProcesses | Stop-Process -Force
    Start-Sleep -Milliseconds 600
}

if (Test-Path -LiteralPath $releaseDir) {
    try {
        Remove-Item -LiteralPath $releaseDir -Recurse -Force
    } catch {
        Write-Host "Release directory root is locked; falling back to in-place refresh..."
        Get-ChildItem -LiteralPath $releaseDir -Force | ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
        }
    }
}
if (Test-Path -LiteralPath $releaseZip) {
    Remove-Item -LiteralPath $releaseZip -Force
}
if (Test-Path -LiteralPath $stageDistRoot) {
    Remove-Item -LiteralPath $stageDistRoot -Recurse -Force
}
if (Test-Path -LiteralPath $workDir) {
    Remove-Item -LiteralPath $workDir -Recurse -Force
}
if (Test-Path -LiteralPath $specDir) {
    Remove-Item -LiteralPath $specDir -Recurse -Force
}

$logoAssets = Join-Path $root "assets/logo"
& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $releaseName `
    --distpath $stageDistRoot `
    --workpath $workDir `
    --specpath $specDir `
    --add-data "${logoAssets};assets/logo" `
    (Join-Path $root "main.py")

if (-not (Test-Path -LiteralPath $stageReleaseDir)) {
    throw "PyInstaller did not create staged release directory: $stageReleaseDir"
}

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
Get-ChildItem -LiteralPath $stageReleaseDir -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $releaseDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $releaseDir "app_data") | Out-Null

if ($resolvedSeedDbPath) {
    Copy-Item -LiteralPath $resolvedSeedDbPath -Destination (Join-Path $releaseDir "exam_trainer.db") -Force
    Write-Host "Bundled seeded database: $resolvedSeedDbPath"
}

Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination (Join-Path $releaseDir "README.md") -Force

$docsPath = Join-Path $root "docs"
if (Test-Path -LiteralPath $docsPath) {
    Copy-Item -LiteralPath $docsPath -Destination (Join-Path $releaseDir "docs") -Recurse -Force
}

$scriptsPath = Join-Path $root "scripts"
if (Test-Path -LiteralPath $scriptsPath) {
    Copy-Item -LiteralPath $scriptsPath -Destination (Join-Path $releaseDir "scripts") -Recurse -Force
}

$gitCommit = ""
try {
    $gitCommit = (git -C $root rev-parse --short=12 HEAD 2>$null | Select-Object -First 1).Trim()
} catch {
    $gitCommit = ""
}
$buildInfo = [ordered]@{
    version = $appVersion
    commit = $gitCommit
    built_at = (Get-Date).ToString("o")
}
$buildInfo | ConvertTo-Json | Set-Content -LiteralPath $buildInfoPath -Encoding UTF8

if (-not $SkipZip) {
    Compress-Archive -LiteralPath $releaseDir -DestinationPath $releaseZip -CompressionLevel Optimal -Force
}

Write-Host "Build completed: $releaseDir"
Write-Host "Packaged README/docs/scripts were copied from repo root."
if (-not $SkipZip) {
    Write-Host "Release archive updated: $releaseZip"
}
