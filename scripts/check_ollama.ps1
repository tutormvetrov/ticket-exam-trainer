$ErrorActionPreference = "Stop"

$modelsPath = [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User")
$ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"

Write-Host "OLLAMA_MODELS: $modelsPath"
Write-Host "Ollama executable: $ollamaExe"

if (-not (Test-Path $ollamaExe)) {
    throw "Ollama executable not found."
}

$env:OLLAMA_MODELS = if ($modelsPath) { $modelsPath } else { "D:\OllamaModels" }

Write-Host "Version:"
& $ollamaExe --version

$existing = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "Starting Ollama server"
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 8
}

Write-Host "Model list:"
& $ollamaExe list

Write-Host "API tags:"
$tags = Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/tags -TimeoutSec 20
$tags.Content

Write-Host "Generate smoke test:"
$body = @{
    model = "mistral:instruct"
    prompt = "Answer in one short sentence: what is active recall?"
    stream = $false
} | ConvertTo-Json

Invoke-WebRequest -UseBasicParsing http://localhost:11434/api/generate -Method Post -ContentType "application/json" -Body $body -TimeoutSec 120 |
    Select-Object -ExpandProperty Content
