$ErrorActionPreference = "Stop"

$modelsPath = [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User")
$legacyModelsPath = Join-Path $HOME ".ollama\\models"
$ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
$baseUrl = "http://localhost:11434"

if (-not $modelsPath) {
    $modelsPath = if (Test-Path "D:\") { "D:\OllamaModels" } else { $legacyModelsPath }
}

function Test-ModelsPresent {
    param([string]$PathToCheck)
    if (-not $PathToCheck) { return $false }
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
    param([int]$TimeoutSec = 25)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-OllamaEndpoint -TimeoutSec 3) {
            return $true
        }
        Start-Sleep -Milliseconds 700
    }
    return $false
}

Write-Host "OLLAMA_MODELS: $modelsPath"
Write-Host "Ollama executable: $ollamaExe"

if (-not (Test-Path $ollamaExe)) {
    throw "Ollama executable not found."
}

if (-not (Test-ModelsPresent -PathToCheck $modelsPath) -and (Test-ModelsPresent -PathToCheck $legacyModelsPath)) {
    Write-Host "Configured models path is empty. Falling back to legacy path: $legacyModelsPath"
    $modelsPath = $legacyModelsPath
}

$env:OLLAMA_MODELS = $modelsPath

Write-Host "Version:"
& $ollamaExe --version

if (-not (Test-OllamaEndpoint -TimeoutSec 3)) {
    Write-Host "Endpoint is down. Starting 'ollama serve'"
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
}

if (-not (Wait-OllamaEndpoint -TimeoutSec 25)) {
    throw "Ollama endpoint did not become ready at $baseUrl"
}

Write-Host "Model list:"
& $ollamaExe list

Write-Host "API tags:"
$tags = Invoke-WebRequest -UseBasicParsing "$baseUrl/api/tags" -TimeoutSec 20
$tags.Content

Write-Host "Generate smoke test:"
$body = @{
    model = "mistral:instruct"
    prompt = "Ответь одним коротким предложением: что такое active recall?"
    stream = $false
} | ConvertTo-Json

Invoke-WebRequest -UseBasicParsing "$baseUrl/api/generate" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 180 |
    Select-Object -ExpandProperty Content
