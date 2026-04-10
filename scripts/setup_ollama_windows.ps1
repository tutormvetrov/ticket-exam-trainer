$ErrorActionPreference = "Stop"

$configuredModelsPath = [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User")
$modelsPath = if ($configuredModelsPath) {
    $configuredModelsPath
} elseif (Test-Path "D:\") {
    "D:\OllamaModels"
} else {
    Join-Path $HOME ".ollama\\models"
}
$legacyModelsPath = Join-Path $HOME ".ollama\\models"
$ollamaDir = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
$ollamaExe = Join-Path $ollamaDir "ollama.exe"
$baseUrl = "http://localhost:11434"

function Test-ModelsPresent {
    param([string]$PathToCheck)
    if (-not (Test-Path $PathToCheck)) { return $false }
    $manifests = Join-Path $PathToCheck "manifests"
    $blobs = Join-Path $PathToCheck "blobs"
    if (-not (Test-Path $manifests) -or -not (Test-Path $blobs)) { return $false }
    $manifestCount = @(Get-ChildItem $manifests -Recurse -File -ErrorAction SilentlyContinue).Count
    $blobCount = @(Get-ChildItem $blobs -File -ErrorAction SilentlyContinue).Count
    return ($manifestCount -gt 0 -and $blobCount -gt 0)
}

function Test-OllamaEndpoint {
    param([int]$TimeoutSec = 5)
    try {
        $response = Invoke-WebRequest -UseBasicParsing "$baseUrl/api/tags" -TimeoutSec $TimeoutSec
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Wait-OllamaEndpoint {
    param([int]$TimeoutSec = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-OllamaEndpoint -TimeoutSec 3) {
            return $true
        }
        Start-Sleep -Milliseconds 700
    }
    return $false
}

Write-Host "Using models directory: $modelsPath"
New-Item -Path $modelsPath -ItemType Directory -Force | Out-Null

if (-not (Test-ModelsPresent -PathToCheck $modelsPath) -and (Test-ModelsPresent -PathToCheck $legacyModelsPath)) {
    Write-Host "Found existing models in legacy path: $legacyModelsPath"
    Write-Host "Copying existing models to target path: $modelsPath"
    Copy-Item -Path (Join-Path $legacyModelsPath "*") -Destination $modelsPath -Recurse -Force
}

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

if (-not (Test-OllamaEndpoint -TimeoutSec 3)) {
    Write-Host "Starting Ollama server via 'ollama serve'"
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
}

if (-not (Wait-OllamaEndpoint -TimeoutSec 30)) {
    throw "Ollama endpoint did not become ready at $baseUrl"
}

Write-Host "Pulling mistral:instruct"
& $ollamaExe pull mistral:instruct

Write-Host "Installed models:"
& $ollamaExe list

Write-Host "API tags:"
Invoke-WebRequest -UseBasicParsing "$baseUrl/api/tags" -TimeoutSec 20 | Select-Object -ExpandProperty Content

Write-Host "Generate smoke test:"
$body = @{
    model = "mistral:instruct"
    prompt = "Ответь одним коротким предложением: что такое active recall?"
    stream = $false
} | ConvertTo-Json

Invoke-WebRequest -UseBasicParsing "$baseUrl/api/generate" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 180 |
    Select-Object -ExpandProperty Content
