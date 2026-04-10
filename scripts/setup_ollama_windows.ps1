$ErrorActionPreference = "Stop"

$modelsPath = "D:\OllamaModels"
$ollamaDir = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
$ollamaExe = Join-Path $ollamaDir "ollama.exe"

Write-Host "Creating model directory: $modelsPath"
New-Item -Path $modelsPath -ItemType Directory -Force | Out-Null

Write-Host "Setting OLLAMA_MODELS for current user"
setx OLLAMA_MODELS $modelsPath | Out-Null
$env:OLLAMA_MODELS = $modelsPath

if (-not (Test-Path $ollamaExe)) {
    Write-Host "Installing Ollama via winget"
    winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
}

if (-not (Test-Path $ollamaExe)) {
    throw "Ollama executable not found after installation."
}

Write-Host "Ollama version:"
& $ollamaExe --version

$existing = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "Starting Ollama server"
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 8
}

Write-Host "Pulling mistral:instruct"
& $ollamaExe pull mistral:instruct

Write-Host "Installed models:"
& $ollamaExe list

Write-Host "API tags:"
Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/tags -TimeoutSec 20 | Select-Object -ExpandProperty Content
