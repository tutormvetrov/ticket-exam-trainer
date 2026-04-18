param(
    [string]$ReleaseDir = "",
    [string]$PythonExe = "python",
    [string]$WorkspaceRoot = ""
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Push-Location $root
try {
    & $PythonExe -m pytest -q tests/contracts tests/journeys tests/visual
    if ($LASTEXITCODE -ne 0) {
        throw "Acceptance pytest suite failed."
    }

    if (-not $ReleaseDir) {
        Write-Host "Acceptance suite passed for source workspace."
        exit 0
    }

    $releaseExe = Join-Path $ReleaseDir "Tezis.exe"
    $buildInfoPath = Join-Path $ReleaseDir "build_info.json"
    if (-not (Test-Path -LiteralPath $releaseExe)) {
        throw "Release executable not found: $releaseExe"
    }
    if (-not (Test-Path -LiteralPath $buildInfoPath)) {
        throw "Release build info missing: $buildInfoPath"
    }

    if (-not $WorkspaceRoot) {
        $WorkspaceRoot = Join-Path $root "build\release-acceptance-workspace"
    }
    if (Test-Path -LiteralPath $WorkspaceRoot) {
        Remove-Item -LiteralPath $WorkspaceRoot -Recurse -Force
    }
    & $PythonExe (Join-Path $root "scripts\build_acceptance_workspace.py") $WorkspaceRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build acceptance workspace."
    }

    $artifactDir = Join-Path $ReleaseDir "acceptance-artifacts"
    New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

    foreach ($view in @("library", "tickets", "training", "dialogue")) {
        $shotPath = Join-Path $artifactDir "$view.png"
        if (Test-Path -LiteralPath $shotPath) {
            Remove-Item -LiteralPath $shotPath -Force
        }

        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $releaseExe
        $startInfo.Arguments = "--screenshot `"$shotPath`" --view $view --theme light --width 1500 --height 920"
        $startInfo.UseShellExecute = $false
        $startInfo.EnvironmentVariables["TEZIS_DISABLE_SPLASH"] = "1"
        $startInfo.EnvironmentVariables["TEZIS_WORKSPACE_ROOT"] = $WorkspaceRoot

        $process = [System.Diagnostics.Process]::Start($startInfo)
        if (-not $process.WaitForExit(30000)) {
            try {
                Stop-Process -Id $process.Id -Force
            } catch {
            }
            throw "Packaged app screenshot timed out for view '$view'."
        }

        if (-not (Test-Path -LiteralPath $shotPath)) {
            throw "Packaged screenshot missing for view '$view': $shotPath"
        }
        $file = Get-Item -LiteralPath $shotPath
        if ($file.Length -lt 40000) {
            throw "Packaged screenshot looks incomplete for view '$view': $shotPath"
        }
    }

    Write-Host "Release acceptance passed."
    Write-Host "Workspace: $WorkspaceRoot"
    Write-Host "Artifacts: $artifactDir"
}
finally {
    Pop-Location
}
