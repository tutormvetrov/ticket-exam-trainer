$ErrorActionPreference = "Stop"

$configuredModelsPath = [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User")
$defaultModelsPath = if (Test-Path "D:\") { "D:\Ollama\models" } else { Join-Path $HOME ".ollama\models" }
$legacySharedModelsPath = "D:\OllamaModels"
$legacyUserModelsPath = Join-Path $HOME ".ollama\models"
$modelsPath = if ($configuredModelsPath) { $configuredModelsPath } else { $defaultModelsPath }
$ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
$baseUrl = "http://localhost:11434"

function Test-ModelsPresent {
    param([string]$PathToCheck)
    if (-not $PathToCheck) { return $false }
    if (-not (Test-Path -LiteralPath $PathToCheck)) { return $false }
    $manifests = Join-Path $PathToCheck "manifests"
    $blobs = Join-Path $PathToCheck "blobs"
    if (-not (Test-Path -LiteralPath $manifests) -or -not (Test-Path -LiteralPath $blobs)) { return $false }
    $manifestCount = @(Get-ChildItem -LiteralPath $manifests -Recurse -File -ErrorAction SilentlyContinue).Count
    $blobCount = @(Get-ChildItem -LiteralPath $blobs -File -ErrorAction SilentlyContinue).Count
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

function Get-HardwareProfile {
    $system = Get-CimInstance Win32_ComputerSystem
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = Get-CimInstance Win32_Processor
    $gpus = @(Get-CimInstance Win32_VideoController | Where-Object { $_.Name })
    $dedicatedGpu = $gpus |
        Where-Object {
            $_.Name -notmatch "Intel|Microsoft Basic|Virtual" -and
            [double]($_.AdapterRAM) -ge 2GB
        } |
        Sort-Object AdapterRAM -Descending |
        Select-Object -First 1

    [pscustomobject]@{
        MemoryGB = [math]::Round([double]$system.TotalPhysicalMemory / 1GB, 1)
        FreeMemoryGB = [math]::Round(([double]$os.FreePhysicalMemory * 1KB) / 1GB, 1)
        CpuThreads = [int](($cpu | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum)
        GpuName = if ($dedicatedGpu) { $dedicatedGpu.Name } elseif ($gpus.Count -gt 0) { $gpus[0].Name } else { "Unknown GPU" }
        DedicatedGpuVRAMGB = if ($dedicatedGpu) { [math]::Round([double]$dedicatedGpu.AdapterRAM / 1GB, 1) } else { 0.0 }
    }
}

function Get-RecommendedModel {
    param($Hardware)

    $tiers = @(
        @{ Model = "qwen3:14b"; MinMemoryGB = 32.0; MinFreeGB = 12.0; MinGpuGB = 10.0 },
        @{ Model = "qwen3:8b"; MinMemoryGB = 20.0; MinFreeGB = 6.0; MinGpuGB = 6.0 },
        @{ Model = "qwen3:4b"; MinMemoryGB = 12.0; MinFreeGB = 2.5; MinGpuGB = 0.0 },
        @{ Model = "qwen3:1.7b"; MinMemoryGB = 8.0; MinFreeGB = 1.25; MinGpuGB = 0.0 },
        @{ Model = "qwen3:0.6b"; MinMemoryGB = 0.0; MinFreeGB = 0.0; MinGpuGB = 0.0 }
    )

    foreach ($tier in $tiers) {
        $hasMemory = $Hardware.MemoryGB -ge $tier.MinMemoryGB
        $hasWorkingSet = $Hardware.FreeMemoryGB -ge $tier.MinFreeGB
        $hasGpuHeadroom = $Hardware.DedicatedGpuVRAMGB -ge $tier.MinGpuGB
        if ($hasMemory -and ($hasWorkingSet -or $hasGpuHeadroom)) {
            return $tier.Model
        }
    }
    return "qwen3:0.6b"
}

Write-Host "OLLAMA_MODELS: $modelsPath"
Write-Host "Ollama executable: $ollamaExe"

if (-not (Test-Path -LiteralPath $ollamaExe)) {
    throw "Ollama executable not found."
}

if (-not (Test-ModelsPresent -PathToCheck $modelsPath)) {
    foreach ($legacyPath in @($legacySharedModelsPath, $legacyUserModelsPath)) {
        if ($legacyPath -ne $modelsPath -and (Test-ModelsPresent -PathToCheck $legacyPath)) {
            Write-Host "Configured models path is empty. Falling back to legacy path: $legacyPath"
            $modelsPath = $legacyPath
            break
        }
    }
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

$hardware = Get-HardwareProfile
$preferredModel = Get-RecommendedModel -Hardware $hardware

Write-Host "Recommended model for this PC: $preferredModel"
Write-Host "Hardware: RAM $($hardware.MemoryGB) GB, free RAM $($hardware.FreeMemoryGB) GB, GPU $($hardware.GpuName), VRAM $($hardware.DedicatedGpuVRAMGB) GB"

Write-Host "Model list:"
& $ollamaExe list

Write-Host "API tags:"
$tags = Invoke-WebRequest -UseBasicParsing "$baseUrl/api/tags" -TimeoutSec 20
$tags.Content

$tagsPayload = $tags.Content | ConvertFrom-Json
$availableModels = @($tagsPayload.models | ForEach-Object { $_.name }) | Where-Object { $_ }
$familyMatches = @($availableModels | Where-Object { $_ -like "qwen3:*" -or $_ -like "*qwen3*" })
$smokeModel = if ($availableModels -contains $preferredModel) {
    $preferredModel
} elseif ($familyMatches.Count -gt 0) {
    $familyMatches[0]
} elseif ($availableModels.Count -gt 0) {
    $availableModels[0]
} else {
    $preferredModel
}

if ($smokeModel -ne $preferredModel) {
    Write-Host "Preferred model '$preferredModel' is not installed. Using smoke-test fallback: $smokeModel"
}

Write-Host "Generate smoke test:"
$body = @{
    model = $smokeModel
    prompt = "Answer in one short sentence: what is active recall?"
    stream = $false
} | ConvertTo-Json

Invoke-WebRequest -UseBasicParsing "$baseUrl/api/generate" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 180 |
    Select-Object -ExpandProperty Content
