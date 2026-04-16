param(
    [string]$ReleaseDir = "",
    [switch]$Rebuild,
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $ReleaseDir) {
    $ReleaseDir = Join-Path $root "dist\Tezis"
}

if ($Rebuild) {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $root "scripts\build_exe.ps1") -PythonExe $PythonExe
}

$releaseExe = Join-Path $ReleaseDir "Tezis.exe"
$screenshotPath = Join-Path $ReleaseDir "release-smoke.png"
$buildInfoPath = Join-Path $ReleaseDir "build_info.json"
$packagedDbPath = Join-Path $ReleaseDir "exam_trainer.db"

if (-not (Test-Path -LiteralPath $releaseExe)) {
    throw "Release executable not found: $releaseExe"
}

if (Test-Path -LiteralPath $screenshotPath) {
    Remove-Item -LiteralPath $screenshotPath -Force
}

Write-Host "Running packaged smoke: $releaseExe"
$process = Start-Process -FilePath $releaseExe -PassThru
try {
    $windowReady = $false
    for ($index = 0; $index -lt 40; $index++) {
        Start-Sleep -Milliseconds 500
        $process.Refresh()
        if ($process.HasExited) {
            throw "Packaged app exited before the main window became available. ExitCode=$($process.ExitCode)"
        }
        if ($process.MainWindowHandle -ne 0) {
            $windowReady = $true
            break
        }
    }

    if (-not $windowReady) {
        throw "Packaged app did not expose a main window handle in time."
    }

    Add-Type -AssemblyName System.Drawing
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class TezisNativeWindow {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
}
"@

    $rect = New-Object TezisNativeWindow+RECT
    $ok = [TezisNativeWindow]::GetWindowRect($process.MainWindowHandle, [ref]$rect)
    if (-not $ok) {
        throw "Failed to read packaged window bounds."
    }

    $width = [Math]::Max(1, $rect.Right - $rect.Left)
    $height = [Math]::Max(1, $rect.Bottom - $rect.Top)
    $bitmap = New-Object System.Drawing.Bitmap $width, $height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
    $bitmap.Save($screenshotPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bitmap.Dispose()
}
finally {
    if ($null -ne $process -and -not $process.HasExited) {
        [void]$process.CloseMainWindow()
        if (-not $process.WaitForExit(5000)) {
            Stop-Process -Id $process.Id -Force
        }
    }
}

if (-not (Test-Path -LiteralPath $screenshotPath)) {
    throw "Packaged app did not produce screenshot: $screenshotPath"
}

if (-not (Test-Path -LiteralPath $buildInfoPath)) {
    throw "Packaged build info is missing: $buildInfoPath"
}
if (Test-Path -LiteralPath $packagedDbPath) {
    throw "Release must not bundle a live workspace database by default: $packagedDbPath"
}

$checks = @(
    @{ Label = "README"; Source = (Join-Path $root "README.md"); Packaged = (Join-Path $ReleaseDir "README.md") },
    @{ Label = "product_spec"; Source = (Join-Path $root "docs\product_spec.md"); Packaged = (Join-Path $ReleaseDir "docs\product_spec.md") },
    @{ Label = "check_ollama"; Source = (Join-Path $root "scripts\check_ollama.ps1"); Packaged = (Join-Path $ReleaseDir "scripts\check_ollama.ps1") }
)

foreach ($item in $checks) {
    $sourceHash = (Get-FileHash -LiteralPath $item.Source -Algorithm SHA256).Hash
    $packagedHash = (Get-FileHash -LiteralPath $item.Packaged -Algorithm SHA256).Hash
    if ($sourceHash -ne $packagedHash) {
        throw "Packaged file is out of sync: $($item.Label)"
    }
}

$buildInfo = Get-Content -LiteralPath $buildInfoPath -Raw | ConvertFrom-Json
$smokeImage = Get-Item -LiteralPath $screenshotPath
$commitLabel = if ($buildInfo.commit) { $buildInfo.commit } else { "source" }

Write-Host "Release smoke passed."
Write-Host ("Build: v{0} commit {1}" -f $buildInfo.version, $commitLabel)
Write-Host ("Built at: {0}" -f $buildInfo.built_at)
Write-Host ("Screenshot: {0} ({1} bytes)" -f $smokeImage.FullName, $smokeImage.Length)

exit 0
