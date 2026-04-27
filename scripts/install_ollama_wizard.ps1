<#
.SYNOPSIS
    Interactive wizard that detects hardware, recommends an Ollama review-model
    tier, installs Ollama if needed, pulls the model, runs a canary, and saves
    the choice to the app settings file.

.DESCRIPTION
    Detects hardware, recommends a local review-model tier, installs Ollama if
    needed, pulls the model, runs a canary, and writes the choice to
    settings.json. The default review-model is `qwen2.5:7b-instruct-q4_K_M`,
    premium tier is
    `vikhr-nemo-12b-instruct` (with `qwen2.5:14b-instruct-q4_K_M` as the
    fallback tag). Light tier (<8 GB RAM) skips Ollama entirely and uses the
    keyword fallback baked into the trainer.

.PARAMETER Tier
    Optional tier override: 'light', 'default', or 'premium'. If omitted, the
    wizard chooses automatically from detected RAM/VRAM and asks for
    confirmation. Accepts 'auto' as an explicit synonym for detect.

.PARAMETER Yes
    Skip the final prompt: accept the recommended/chosen tier and proceed.

.PARAMETER DryRun
    Detect hardware, print the decision, but DO NOT install Ollama, pull any
    model, run the canary, or mutate settings.json. Safe to run on any machine.

.PARAMETER SettingsPath
    Override the destination settings file. By default resolves to
    `$env:LOCALAPPDATA\Tezis\app_data\settings.json` (see app/paths.py).

.EXAMPLE
    .\scripts\install_ollama_wizard.ps1 -DryRun
    .\scripts\install_ollama_wizard.ps1 -Tier default -Yes
    .\scripts\install_ollama_wizard.ps1

.NOTES
    Run as normal user. Winget will elevate itself for Ollama install. Safe to
    run twice: re-running detects existing Ollama/models and skips redundant
    work (idempotent).
#>
[CmdletBinding()]
param(
    [ValidateSet('auto','light','default','premium','ask')]
    [string]$Tier = 'auto',

    [switch]$Yes,

    [switch]$DryRun,

    [string]$SettingsPath = ''
)

$ErrorActionPreference = 'Stop'

$script:TierCatalog = @{
    light = @{
        Name      = 'Light'
        Model     = ''
        MinRamGB  = 0.0
        MinVramGB = 0.0
        Latency   = '<1 s (keyword fallback, без LLM)'
        Notes     = 'Ollama не требуется; рецензия работает на keyword-наборе.'
    }
    default = @{
        Name      = 'Default'
        Model     = 'qwen2.5:7b-instruct-q4_K_M'
        MinRamGB  = 8.0
        MinVramGB = 0.0
        Latency   = '25-45 s (CPU)'
        Notes     = 'Рекомендация после research 2026-04-19.'
    }
    premium = @{
        Name             = 'Premium'
        Model            = 'vikhr-nemo-12b-instruct'
        ModelFallback    = 'qwen2.5:14b-instruct-q4_K_M'
        MinRamGB         = 16.0
        MinVramGB        = 8.0
        Latency          = '35-60 s (GPU)'
        Notes            = 'Лучший RU-respond. Если тег vikhr-nemo недоступен в registry — fallback на qwen2.5:14b-q4_K_M.'
    }
}

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Write-Info {
    param([string]$Text)
    Write-Host "    $Text"
}

function Write-Note {
    param([string]$Text)
    Write-Host "    $Text" -ForegroundColor DarkGray
}

function Write-WarnLine {
    param([string]$Text)
    Write-Host "    ! $Text" -ForegroundColor Yellow
}

function Write-OkLine {
    param([string]$Text)
    Write-Host "    ok $Text" -ForegroundColor Green
}

function Write-FailLine {
    param([string]$Text)
    Write-Host "    x $Text" -ForegroundColor Red
}

function Get-TierDisplayName {
    param([string]$TierKey)
    switch ($TierKey) {
        'light'   { return 'без ИИ' }
        'default' { return 'обычный' }
        'premium' { return 'лучший' }
        default   { return $TierKey }
    }
}

function Resolve-DisplayNameToTier {
    param([string]$DisplayName)
    switch ($DisplayName.ToLowerInvariant().Trim()) {
        'без ии'  { return 'light' }
        'без ai'  { return 'light' }
        'light'   { return 'light' }
        'обычный' { return 'default' }
        'default' { return 'default' }
        'лучший'  { return 'premium' }
        'premium' { return 'premium' }
        default   { return '' }
    }
}

function Get-HardwareSnapshot {
    $ram = [math]::Round([double](Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
    $cpuCores = [int](Get-CimInstance Win32_Processor |
        Measure-Object -Property NumberOfCores -Sum | Select-Object -ExpandProperty Sum)
    $cpuLogical = [int](Get-CimInstance Win32_Processor |
        Measure-Object -Property NumberOfLogicalProcessors -Sum | Select-Object -ExpandProperty Sum)

    $gpus = @(Get-CimInstance Win32_VideoController |
        Where-Object { $_.AdapterRAM -gt 0 })
    $topGpu = $gpus | Sort-Object AdapterRAM -Descending | Select-Object -First 1
    $vramReported = if ($topGpu) {
        [math]::Round([double]$topGpu.AdapterRAM / 1GB, 1)
    } else { 0.0 }

    # AdapterRAM is reported via a UInt32 surface on Win32_VideoController —
    # ~4 GB is the ceiling. Any value at/above that is suspicious: could be a
    # truly 4 GB card or a 6/8/12 GB card that got clipped. Warn either way.
    # Try to get accurate VRAM from nvidia-smi (avoids the Win32 4 GB ceiling on UInt32 surface)
    $vramActual = $vramReported
    $vramSource = 'Windows API'
    try {
        $smiRaw = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0 -and $smiRaw) {
            $smiMib = [int](($smiRaw -split "`n")[0].Trim())
            $vramActual = [math]::Round($smiMib / 1024.0, 1)
            $vramSource = 'nvidia-smi'
        }
    } catch {}

    [pscustomobject]@{
        RamGB        = $ram
        CpuCores     = $cpuCores
        CpuLogical   = $cpuLogical
        GpuName      = if ($topGpu) { $topGpu.Name } else { 'Unknown / integrated' }
        VramGB       = $vramReported
        VramActualGB = $vramActual
        VramSource   = $vramSource
    }
}

function Select-RecommendedTier {
    param($Hardware)

    if ($Hardware.RamGB -lt 8.0) {
        return 'light'
    }
    if ($Hardware.RamGB -ge 16.0 -and $Hardware.VramActualGB -ge 8.0) {
        return 'premium'
    }
    return 'default'
}

function Show-TierTable {
    param([string]$RecommendedTier, $Hardware)
    $ram  = $Hardware.RamGB
    $vram = $Hardware.VramActualGB

    Write-Info "  без ИИ   — ИИ не используется. Тезис покажет эталонный ответ,"
    Write-Info "             сравнивай сам. Быстро, но без обратной связи."
    Write-Info "             Подходит: если RAM меньше 8 ГБ или рецензия не нужна."
    Write-Info ""
    Write-Info "  обычный  — ИИ работает на процессоре. Ответ примерно через 30 секунд."
    Write-Info "             Скачать: ~4 ГБ  ·  Модель: qwen2.5:7b (русский и английский)"
    Write-Info "             Подходит: если RAM 8–16 ГБ или видеокарта слабая."
    Write-Info ""
    Write-Info "  лучший   — ИИ работает на видеокарте. Ответ ~10–15 секунд,"
    Write-Info "             модель заточена под русский язык."
    Write-Info "             Скачать: ~8 ГБ  ·  Модель: vikhr-nemo-12b"
    Write-Info "             Подходит: если RAM 16+ ГБ и VRAM 8+ ГБ."
}

function Prompt-Tier {
    param([string]$Default)
    $displayDefault = Get-TierDisplayName -TierKey $Default
    while ($true) {
        $answer = Read-Host "Режим [без ИИ / обычный / лучший]  Enter = $displayDefault  ·  Q = выход"
        if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
        $answer = $answer.Trim()
        if ($answer -eq 'q' -or $answer -eq 'Q') { return '' }
        $resolved = Resolve-DisplayNameToTier -DisplayName $answer
        if ($resolved) { return $resolved }
        Write-WarnLine "Введи: без ИИ, обычный или лучший (или пустую строку для '$displayDefault')."
    }
}

function Resolve-SettingsPath {
    param([string]$Override)
    if ($Override) {
        $resolved = Resolve-Path -LiteralPath $Override -ErrorAction SilentlyContinue
        if ($resolved) { return $resolved.Path }
        # Если каталога ещё нет, возвращаем путь как есть — create-on-write сделает Save-SettingsChoice.
        return $Override
    }
    $localAppData = $env:LOCALAPPDATA
    if (-not $localAppData) {
        $localAppData = Join-Path $env:USERPROFILE 'AppData\Local'
    }
    return Join-Path $localAppData 'Tezis\app_data\settings.json'
}

function Test-OllamaCli {
    # 1. Already in PATH
    if (Get-Command ollama -ErrorAction SilentlyContinue) { return $true }

    # 2. Refresh PATH from registry — catches apps installed in this same session
    $machinePath = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath    = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $env:PATH    = (($machinePath, $userPath | Where-Object { $_ }) -join ';')
    if (Get-Command ollama -ErrorAction SilentlyContinue) { return $true }

    # 3. Search registry uninstall entries — works for any drive / custom location
    $regRoots = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'
    )
    foreach ($root in $regRoots) {
        if (-not (Test-Path $root)) { continue }
        $entry = Get-ChildItem $root -ErrorAction SilentlyContinue |
            Get-ItemProperty -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -like '*Ollama*' } |
            Select-Object -First 1
        if (-not $entry) { continue }
        $installDir = $entry.InstallLocation
        if ($installDir -and (Test-Path -LiteralPath (Join-Path $installDir 'ollama.exe'))) {
            $env:PATH = "$installDir;$env:PATH"
            return $true
        }
    }

    return $false
}

function Test-OllamaEndpoint {
    param([int]$TimeoutSec = 5)
    try {
        $resp = Invoke-WebRequest -UseBasicParsing 'http://localhost:11434/api/tags' -TimeoutSec $TimeoutSec
        return $resp.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Wait-OllamaEndpoint {
    param([int]$TimeoutSec = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-OllamaEndpoint -TimeoutSec 3) { return $true }
        Start-Sleep -Milliseconds 700
    }
    return $false
}

function Get-InstalledOllamaModels {
    if (-not (Test-OllamaEndpoint -TimeoutSec 3)) { return @() }
    try {
        $raw = Invoke-WebRequest -UseBasicParsing 'http://localhost:11434/api/tags' -TimeoutSec 8
        $payload = $raw.Content | ConvertFrom-Json
        return @($payload.models | ForEach-Object { $_.name })
    } catch {
        return @()
    }
}

function Install-OllamaIfMissing {
    param([switch]$DryRun)

    if (Test-OllamaCli) {
        Write-OkLine "Ollama уже установлена: $((ollama --version 2>&1) -join ' ')"
        return $true
    }

    Write-WarnLine "Ollama не найдена в PATH."
    if ($DryRun) {
        Write-Note "DryRun: сделал бы `winget install Ollama.Ollama` либо скачал OllamaSetup.exe."
        return $false
    }

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Info "Запускаю winget install Ollama.Ollama (установщик может попросить UAC)…"
        try {
            & winget install --id Ollama.Ollama -e `
                --accept-package-agreements `
                --accept-source-agreements
            if ($LASTEXITCODE -ne 0) {
                throw "winget вышел с кодом $LASTEXITCODE"
            }
            Write-OkLine "winget install Ollama.Ollama завершён."
            return $true
        } catch {
            Write-WarnLine "winget не сработал: $($_.Exception.Message). Переключаюсь на прямую загрузку."
        }
    } else {
        Write-WarnLine "winget не найден. Переключаюсь на прямую загрузку OllamaSetup.exe."
    }

    $setupPath = Join-Path $env:TEMP 'OllamaSetup.exe'
    try {
        Write-Info "Скачиваю $setupPath …"
        & curl.exe -L -o $setupPath 'https://ollama.com/download/OllamaSetup.exe'
        if ($LASTEXITCODE -ne 0) { throw "curl вышел с кодом $LASTEXITCODE" }
        Write-Info "Запускаю инсталлятор (UI может попросить UAC)…"
        & $setupPath /SILENT
        if ($LASTEXITCODE -ne 0) {
            Write-WarnLine "Silent install вышел с $LASTEXITCODE — попробуйте запустить $setupPath вручную."
        }
        return (Test-OllamaCli)
    } catch {
        Write-FailLine "Не удалось установить Ollama автоматически: $($_.Exception.Message)"
        Write-Note "Установите руками: https://ollama.com/download, затем перезапустите мастер."
        return $false
    }
}

function Ensure-OllamaServer {
    param([switch]$DryRun)

    if (Test-OllamaEndpoint -TimeoutSec 3) {
        Write-OkLine "Ollama endpoint готов на http://localhost:11434."
        return $true
    }

    if ($DryRun) {
        Write-Note "DryRun: запустил бы 'ollama serve' в фоне."
        return $false
    }

    if (-not (Test-OllamaCli)) {
        Write-FailLine "Ollama не установлена — нечего запускать."
        return $false
    }

    Write-Info "Запускаю 'ollama serve' в фоне…"
    Start-Process -FilePath 'ollama' -ArgumentList 'serve' -WindowStyle Hidden | Out-Null
    if (Wait-OllamaEndpoint -TimeoutSec 30) {
        Write-OkLine "Endpoint отвечает."
        return $true
    }
    Write-FailLine "Endpoint не поднялся за 30 секунд."
    return $false
}

function Resolve-ModelTag {
    param(
        [string]$TierKey,
        [string[]]$InstalledModels
    )
    $tier = $script:TierCatalog[$TierKey]
    if (-not $tier.Model) { return '' }

    # Premium: если vikhr-nemo нет в registry / локально — фолбэк на qwen2.5:14b.
    if ($TierKey -eq 'premium') {
        if ($InstalledModels -contains $tier.Model) { return $tier.Model }
        if ($InstalledModels -contains $tier.ModelFallback) { return $tier.ModelFallback }
        return $tier.Model
    }
    return $tier.Model
}

function Invoke-ModelPull {
    param(
        [string]$Model,
        [switch]$DryRun
    )
    if (-not $Model) { return $true }

    $installed = Get-InstalledOllamaModels
    if ($installed -contains $Model) {
        Write-OkLine "Модель '$Model' уже скачана."
        return $true
    }

    if ($DryRun) {
        Write-Note "DryRun: выполнил бы 'ollama pull $Model' (первый pull — несколько минут и ГБ трафика)."
        return $false
    }

    Write-Info "Скачиваю '$Model' через 'ollama pull' (progress видно ниже)…"
    try {
        & ollama pull $Model
        if ($LASTEXITCODE -ne 0) {
            throw "ollama pull вышел с кодом $LASTEXITCODE (возможно, тега нет в registry)"
        }
        Write-OkLine "Pull '$Model' завершён."
        return $true
    } catch {
        Write-FailLine "Не удалось скачать '$Model': $($_.Exception.Message)"
        return $false
    }
}

function Invoke-CanaryTest {
    param(
        [string]$Model,
        [switch]$DryRun
    )
    if (-not $Model) {
        Write-Note "Light tier: canary-тест не нужен (LLM не используется)."
        return $true
    }

    if ($DryRun) {
        Write-Note "DryRun: сделал бы POST /api/generate '$Model' с таймаутом 30s."
        return $true
    }

    Write-Info "Запускаю canary-тест (одно короткое слово, 30 s timeout)…"
    $body = @{
        model       = $Model
        prompt      = "Ответь одним словом по-русски: да"
        stream      = $false
        options     = @{ num_predict = 8 }
    } | ConvertTo-Json -Depth 4

    try {
        $resp = Invoke-WebRequest -UseBasicParsing `
            -Uri 'http://localhost:11434/api/generate' `
            -Method Post `
            -ContentType 'application/json' `
            -Body $body `
            -TimeoutSec 30
        $payload = $resp.Content | ConvertFrom-Json
        $raw = if ($payload.PSObject.Properties.Name -contains 'response') { $payload.response } else { '' }
        if (-not $raw) { $raw = '' }
        $answer = ([string]$raw).Trim()
        if (-not $answer) {
            Write-WarnLine "Canary: модель ответила пустой строкой."
            return $false
        }
        Write-OkLine "Canary ответ: '$answer'"
        return $true
    } catch {
        Write-WarnLine "Canary упал: $($_.Exception.Message)"
        return $false
    }
}

function Save-SettingsChoice {
    param(
        [string]$SettingsFile,
        [string]$Tier,
        [string]$Model,
        [switch]$DryRun
    )

    # Храним как ordered hashtable, чтобы и PS 5.1 (без -AsHashtable), и PS 7+
    # одинаково раскладывали ключи. Конвертируем из PSCustomObject руками.
    $payload = [ordered]@{}
    if (Test-Path -LiteralPath $SettingsFile) {
        try {
            $raw = Get-Content -LiteralPath $SettingsFile -Raw -Encoding UTF8
            if ($raw) {
                $existing = $raw | ConvertFrom-Json
                if ($existing) {
                    foreach ($prop in $existing.PSObject.Properties) {
                        $payload[$prop.Name] = $prop.Value
                    }
                }
            }
        } catch {
            Write-WarnLine "Не смог прочитать $SettingsFile : $($_.Exception.Message). Создам заново."
            $payload = [ordered]@{}
        }
    }

    # Храним выбор тира плюс фактический Ollama-model tag; trainer при запуске
    # читает обе ручки. Model='' для light-тира сбрасывает LLM-рецензию.
    $payload['model'] = $Model
    $payload['review_tier'] = $Tier
    $payload['model_selected_at'] = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')

    if ($DryRun) {
        Write-Note "DryRun: записал бы в $SettingsFile :"
        Write-Note "  tier=$Tier"
        Write-Note "  model=$Model"
        return
    }

    $targetDir = Split-Path -Parent $SettingsFile
    if (-not (Test-Path -LiteralPath $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    $json = $payload | ConvertTo-Json -Depth 8
    Set-Content -LiteralPath $SettingsFile -Value $json -Encoding UTF8
    Write-OkLine "Settings обновлены: $SettingsFile"
}

# -----------------------------------------------------------------------------
# Main flow
# -----------------------------------------------------------------------------

Write-Step "Шаг 1: смотрю, что у тебя за компьютер"
$hardware = Get-HardwareSnapshot
Write-Info "RAM: $($hardware.RamGB) ГБ  ·  CPU: $($hardware.CpuCores) ядер  ·  GPU: $($hardware.GpuName)"
Write-Info ""
if ($hardware.GpuName -notlike '*Unknown*' -and $hardware.GpuName -notlike '*integrated*') {
    Write-Info "Видеокарта есть — это хорошо, ИИ на GPU работает быстрее."
    Write-Info ""
}
if ($hardware.VramSource -eq 'nvidia-smi' -and $hardware.VramActualGB -gt $hardware.VramGB + 0.5) {
    Write-Info "VRAM: $($hardware.VramActualGB) ГБ (nvidia-smi; Windows API сообщал $($hardware.VramGB) ГБ)"
} elseif ($hardware.VramActualGB -gt 0) {
    Write-Info "VRAM: $($hardware.VramActualGB) ГБ"
}

Write-Step "Шаг 2: подбираю подходящий режим рецензирования"
$autoTier = Select-RecommendedTier -Hardware $hardware
$selectedTier = $null

switch ($Tier.ToLowerInvariant()) {
    'auto' { $selectedTier = $autoTier }
    'ask'  { $selectedTier = $autoTier }
    default {
        if ($script:TierCatalog.ContainsKey($Tier)) {
            $selectedTier = $Tier
        } else {
            Write-WarnLine "Неизвестный режим '$Tier', использую авторекомендацию."
            $selectedTier = $autoTier
        }
    }
}

$tierInfo = $script:TierCatalog[$selectedTier]
$displaySelected = Get-TierDisplayName -TierKey $selectedTier

Write-Info "Рецензирование — это когда ты пишешь ответ на билет, а ИИ"
Write-Info "читает его и говорит: что упустил, где ошибся, насколько полно"
Write-Info "раскрыл тему. Всё работает на твоём компьютере, без интернета."
Write-Info ""
Write-Info "Три режима на выбор:"
Write-Info ""

if (-not $Yes) {
    Show-TierTable -RecommendedTier $selectedTier -Hardware $hardware
    Write-Info ""
    Write-Info "Рекомендую: $displaySelected"
    $reasonRam  = "$($hardware.RamGB) ГБ RAM"
    $reasonVram = "$($hardware.VramActualGB) ГБ VRAM"
    Write-Note "($reasonRam + $reasonVram — всё сходится)"
    Write-Info ""
    $override = Prompt-Tier -Default $selectedTier
    if (-not $override) {
        Write-WarnLine "Отмена по запросу пользователя."
        exit 2
    }
    if ($override -ne $selectedTier) {
        $selectedTier = $override
        $tierInfo = $script:TierCatalog[$selectedTier]
        $displaySelected = Get-TierDisplayName -TierKey $selectedTier
        Write-Info "Хорошо, использую режим: $displaySelected"
    }
} else {
    Write-Info "Выбранный режим: $displaySelected ($reasonRam + $reasonVram)"
}

Write-Step "Шаг 3: установка Ollama (если нужна)"
if ($selectedTier -eq 'light') {
    Write-Info "Light-тир: Ollama не обязательна. Пропускаю install/pull/canary."
} else {
    $ollamaOk = Install-OllamaIfMissing -DryRun:$DryRun
    if (-not $ollamaOk -and -not $DryRun) {
        Write-FailLine "Без Ollama продолжить нельзя. Установите её вручную и повторите запуск."
        exit 3
    }

    Write-Step "Шаг 4: запуск ollama serve (если не запущен)"
    $serverOk = Ensure-OllamaServer -DryRun:$DryRun
    if (-not $serverOk -and -not $DryRun) {
        Write-FailLine "Endpoint http://localhost:11434 не отвечает. Запустите 'ollama serve' руками и повторите."
        exit 4
    }

    $installed = @()
    if (-not $DryRun) { $installed = Get-InstalledOllamaModels }
    $modelTag = Resolve-ModelTag -TierKey $selectedTier -InstalledModels $installed

    Write-Step "Шаг 5: pull модели '$modelTag'"
    $pullOk = Invoke-ModelPull -Model $modelTag -DryRun:$DryRun
    if (-not $pullOk -and -not $DryRun) {
        Write-WarnLine "Pull не удался. Возможно, тега нет в registry или сеть недоступна."
        if ($selectedTier -eq 'premium' -and $modelTag -eq $tierInfo.Model) {
            Write-Info "Пробую фолбэк '$($tierInfo.ModelFallback)'…"
            $modelTag = $tierInfo.ModelFallback
            $pullOk = Invoke-ModelPull -Model $modelTag -DryRun:$DryRun
        }
        if (-not $pullOk) {
            Write-FailLine "Финальный pull не удался. Настройка прерывается."
            exit 5
        }
    }

    Write-Step "Шаг 6: canary-тест"
    $null = Invoke-CanaryTest -Model $modelTag -DryRun:$DryRun
}

Write-Step "Шаг 7: запись выбора в settings.json"
$settingsFile = Resolve-SettingsPath -Override $SettingsPath
$modelForSettings = if ($selectedTier -eq 'light') { '' } else { (Resolve-ModelTag -TierKey $selectedTier -InstalledModels (Get-InstalledOllamaModels)) }
Save-SettingsChoice `
    -SettingsFile $settingsFile `
    -Tier $selectedTier `
    -Model $modelForSettings `
    -DryRun:$DryRun

Write-Host ""
Write-Host "Готово." -ForegroundColor Green
$displayFinal = Get-TierDisplayName -TierKey $selectedTier
Write-Info "Режим рецензирования: $displayFinal"
if ($modelForSettings) {
    Write-Info "Модель: $modelForSettings"
} else {
    Write-Info "ИИ не используется — Тезис будет показывать эталонные ответы."
}
Write-Info "Настройки сохранены в: $settingsFile"
if ($DryRun) {
    Write-Note "(DryRun — ничего не устанавливалось и не записывалось)"
}
