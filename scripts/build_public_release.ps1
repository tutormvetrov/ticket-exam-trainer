param(
    [Parameter(Mandatory = $true)][string]$SourcePdf,
    [string]$PythonExe = "python",
    [string]$SeedDatabasePath = "",
    [string]$SummaryJsonPath = "",
    [string]$ArtifactSeedPath = "",
    [switch]$SkipVerify,
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$buildRoot = Join-Path $root "build"
$demoSeedDir = Join-Path $buildRoot "demo_seed"
$releaseArtifactDir = Join-Path $buildRoot "release_artifacts"

if (-not $SeedDatabasePath) {
    $SeedDatabasePath = Join-Path $demoSeedDir "state_exam_public_admin_demo.db"
}
if (-not $SummaryJsonPath) {
    $SummaryJsonPath = Join-Path $demoSeedDir "state_exam_public_admin_demo.manifest.json"
}
if (-not $ArtifactSeedPath) {
    $ArtifactSeedPath = Join-Path $releaseArtifactDir "state_exam_public_admin_demo.db"
}

if (-not (Test-Path -LiteralPath $SourcePdf)) {
    throw "Source PDF not found: $SourcePdf"
}

$resolvedSourcePdf = (Resolve-Path -LiteralPath $SourcePdf).Path

Write-Host "=== Step 1/4: Build seed database from PDF ==="
Write-Host "Source PDF:   $resolvedSourcePdf"
Write-Host "Output DB:    $SeedDatabasePath"
Write-Host "Manifest:     $SummaryJsonPath"

New-Item -ItemType Directory -Force -Path $demoSeedDir | Out-Null
New-Item -ItemType Directory -Force -Path $releaseArtifactDir | Out-Null

& $PythonExe (Join-Path $root "scripts\build_state_exam_seed.py") `
    --source-pdf $resolvedSourcePdf `
    --output-db $SeedDatabasePath `
    --summary-json $SummaryJsonPath
if ($LASTEXITCODE -ne 0) {
    throw "build_state_exam_seed.py failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path -LiteralPath $SeedDatabasePath)) {
    throw "Seed database was not produced: $SeedDatabasePath"
}
if (-not (Test-Path -LiteralPath $SummaryJsonPath)) {
    throw "Seed manifest was not produced: $SummaryJsonPath"
}

if (-not $SkipVerify) {
    Write-Host ""
    Write-Host "=== Step 2/4: Verify seed database trainability ==="
    & $PythonExe (Join-Path $root "scripts\verify_state_exam_seed.py") --seed-db $SeedDatabasePath
    if ($LASTEXITCODE -ne 0) {
        throw "verify_state_exam_seed.py failed with exit code $LASTEXITCODE"
    }
} else {
    Write-Host ""
    Write-Host "=== Step 2/4: Verification skipped by flag ==="
}

Write-Host ""
Write-Host "=== Step 3/4: Build Windows release with seed ==="
$buildExeArgs = @("-PythonExe", $PythonExe, "-SeedDatabasePath", $SeedDatabasePath)
if ($SkipZip) {
    $buildExeArgs += "-SkipZip"
}
& powershell -ExecutionPolicy Bypass -File (Join-Path $root "scripts\build_exe.ps1") @buildExeArgs
if ($LASTEXITCODE -ne 0) {
    throw "build_exe.ps1 failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "=== Step 4/4: Stage seed artifact for macOS builder ==="
Copy-Item -LiteralPath $SeedDatabasePath -Destination $ArtifactSeedPath -Force
$artifactManifest = Join-Path $releaseArtifactDir "state_exam_public_admin_demo.manifest.json"
Copy-Item -LiteralPath $SummaryJsonPath -Destination $artifactManifest -Force
Write-Host "Seed artifact:    $ArtifactSeedPath"
Write-Host "Manifest artifact: $artifactManifest"

$manifest = Get-Content -LiteralPath $SummaryJsonPath -Raw | ConvertFrom-Json
Write-Host ""
Write-Host "Public release ready:"
Write-Host ("  Documents: {0}" -f $manifest.documents)
Write-Host ("  Tickets:   {0}" -f $manifest.tickets)
Write-Host ("  Sections:  {0}" -f $manifest.sections)
Write-Host ("  Model:     {0}" -f $manifest.model_used)
Write-Host ("  Checksum:  {0}" -f $manifest.checksum_sha256)

exit 0
