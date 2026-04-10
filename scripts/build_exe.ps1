param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $root "dist"
$buildRoot = Join-Path $root "build"
$releaseName = "TicketExamTrainer"
$releaseDir = Join-Path $distRoot $releaseName
$workDir = Join-Path $buildRoot "pyinstaller"
$specDir = Join-Path $buildRoot "spec"

Write-Host "Building release into $releaseDir"

if (Test-Path -LiteralPath $releaseDir) {
    Remove-Item -LiteralPath $releaseDir -Recurse -Force
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
    --distpath $distRoot `
    --workpath $workDir `
    --specpath $specDir `
    (Join-Path $root "main.py")

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
