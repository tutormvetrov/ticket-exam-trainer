param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $root "dist"
$buildRoot = Join-Path $root "build"
$releaseName = "Tezis"
$releaseDir = Join-Path $distRoot $releaseName
$stageDistRoot = Join-Path $buildRoot "release_stage"
$stageReleaseDir = Join-Path $stageDistRoot $releaseName
$workDir = Join-Path $buildRoot "pyinstaller"
$specDir = Join-Path $buildRoot "spec"

Write-Host "Building release into $releaseDir"

if (Test-Path -LiteralPath $releaseDir) {
    Get-ChildItem -LiteralPath $releaseDir -Force | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }
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

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $releaseName `
    --distpath $stageDistRoot `
    --workpath $workDir `
    --specpath $specDir `
    (Join-Path $root "main.py")

if (-not (Test-Path -LiteralPath $stageReleaseDir)) {
    throw "PyInstaller did not create staged release directory: $stageReleaseDir"
}

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
Get-ChildItem -LiteralPath $stageReleaseDir -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $releaseDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $releaseDir "app_data") | Out-Null

Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination (Join-Path $releaseDir "README.md") -Force

$docsPath = Join-Path $root "docs"
if (Test-Path -LiteralPath $docsPath) {
    Copy-Item -LiteralPath $docsPath -Destination (Join-Path $releaseDir "docs") -Recurse -Force
}

$scriptsPath = Join-Path $root "scripts"
if (Test-Path -LiteralPath $scriptsPath) {
    Copy-Item -LiteralPath $scriptsPath -Destination (Join-Path $releaseDir "scripts") -Recurse -Force
}

Write-Host "Build completed: $releaseDir"
