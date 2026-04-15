param(
    [switch]$FullClean
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "Default clean removes only transient build/cache artifacts."
if ($FullClean) {
    Write-Host "Full clean enabled: dist output will also be removed."
}

$dirsToRemove = @(
    (Join-Path $root ".pytest_cache"),
    (Join-Path $root "__pycache__"),
    (Join-Path $root "build")
)

if ($FullClean) {
    $dirsToRemove += (Join-Path $root "dist")
}

$dirsToRemove += Get-ChildItem -Path $root -Recurse -Directory -Force |
    Where-Object { $_.Name -eq "__pycache__" } |
    Select-Object -ExpandProperty FullName

$filesToRemove = @(
    "library-check.png",
    "library-final-check.png",
    "library-postfix-check.png",
    "library-shot-win-8.png",
    "settings-check.png",
    "settings-final-check.png",
    "stage2-structure-check.png",
    "stage3-library-after.png",
    "stage3-library-before.png",
    "stage3-library-delay.png",
    "stage3-settings-after.png",
    "stage3-settings-before.png",
    "stage3-settings-delay.png",
    "statistics-check.png",
    "statistics-final-check.png",
    "statistics-postfix-check.png",
    "tickets-check.png",
    "tickets-final-check.png",
    "training-check.png",
    "training-final-check.png",
    "ui-smoke-stage3.png",
    "user-fix-library.png",
    "user-fix-settings-2.png",
    "user-fix-settings-3.png",
    "user-fix-settings-4.png",
    "user-fix-settings-5.png",
    "user-fix-settings-6.png",
    "user-fix-settings-bottom.png",
    "user-fix-settings.png",
    "seed-run.log"
)

foreach ($dir in $dirsToRemove | Select-Object -Unique) {
    if (Test-Path -LiteralPath $dir) {
        Remove-Item -LiteralPath $dir -Recurse -Force
    }
}

foreach ($name in $filesToRemove) {
    $path = Join-Path $root $name
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

Write-Host "Project cleanup completed."
if ($FullClean) {
    Write-Host "Full clean also removed dist output."
}
