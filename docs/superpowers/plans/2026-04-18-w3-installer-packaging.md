# W3: Installer & Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать Windows-дистрибутив Tezis v2.0: Ollama-установочный мастер с hardware detection и tiered model recommendations, `flet pack` exe, zip-bundle с seed DB и README для однокурсников. Протестировать на 2 чистых VM.

**Architecture:** PowerShell wizard детектит железо, рекомендует qwen3-тир (0.6b / 1.7b / 4b / 8b), устанавливает Ollama (если нет) и модель. Затем `flet pack` собирает exe из `ui_flet/main.py`. `package_release.ps1` кладёт exe + wizard + seed DB в zip.

**Tech Stack:** PowerShell 5+, Ollama CLI, Flet ≥ 0.24, `flet pack` (PyInstaller wrapper), Windows testing VMs

**Ref spec:** `docs/superpowers/specs/2026-04-18-flet-migration-design.md` (Часть 5, 6)

**Worktree:** `D:\ticket-exam-trainer-installer`, ветка `installer` от тэга `v1.2.0`

**⚠️ Dependency:** Финальная upbor default-модели — из R0 validation (Coordinator Day 0). До этого используем placeholder qwen3:1.7b.

---

## Task 1: Hardware Detection Script

**Files:**
- Create: `scripts/install_ollama_wizard.ps1`
- Create: `scripts/lib/hardware_detect.ps1`
- Test: ручная проверка на 1-2 машинах

- [ ] **Step 1: Hardware detection function**

Создать `scripts/lib/hardware_detect.ps1`:

```powershell
# scripts/lib/hardware_detect.ps1
# Detects hardware for model tier recommendation

function Get-SystemHardware {
    $ram_gb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)

    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $cpu_cores = $cpu.NumberOfCores
    $cpu_name = $cpu.Name.Trim()

    # Выбираем GPU с наибольшим VRAM — дискретная обычно имеет больше чем встроенная
    $gpu = Get-CimInstance Win32_VideoController |
        Where-Object { $_.AdapterRAM -gt 0 } |
        Sort-Object AdapterRAM -Descending |
        Select-Object -First 1

    if ($gpu) {
        # Win32_VideoController.AdapterRAM — 32-bit, некорректен для 4+GB карт
        $vram_gb = [math]::Round($gpu.AdapterRAM / 1GB, 1)
        $gpu_name = $gpu.Name

        # Попытаемся получить точный VRAM через nvidia-smi если NVIDIA
        if ($gpu_name -match "NVIDIA") {
            try {
                $nvidia_output = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $nvidia_mb = [int]($nvidia_output -split "`n")[0].Trim()
                    $vram_gb = [math]::Round($nvidia_mb / 1024, 1)
                }
            } catch { }
        }
    } else {
        $vram_gb = 0
        $gpu_name = "Integrated graphics"
    }

    return [PSCustomObject]@{
        RAM_GB = $ram_gb
        CPU_Cores = $cpu_cores
        CPU_Name = $cpu_name
        GPU_Name = $gpu_name
        VRAM_GB = $vram_gb
    }
}

function Recommend-ModelTier {
    param([PSCustomObject]$Hardware)

    # Logic:
    # - VRAM >= 8 && RAM >= 16: qwen3:8b — best quality, GPU-accelerated
    # - VRAM >= 6 && RAM >= 16: qwen3:4b — good quality with GPU
    # - RAM >= 8: qwen3:1.7b — default, CPU fallback OK
    # - RAM < 8: qwen3:0.6b — degraded but functional

    if ($Hardware.VRAM_GB -ge 8 -and $Hardware.RAM_GB -ge 16) {
        return [PSCustomObject]@{
            Tier = "full"
            Model = "qwen3:8b"
            Rationale = "$($Hardware.RAM_GB)ГБ RAM + $($Hardware.VRAM_GB)ГБ VRAM — можем позволить полную модель"
            ExpectedTime = "5-15 сек на рецензию"
            DownloadSize = "5 ГБ"
        }
    }
    if ($Hardware.VRAM_GB -ge 6 -and $Hardware.RAM_GB -ge 16) {
        return [PSCustomObject]@{
            Tier = "advanced"
            Model = "qwen3:4b"
            Rationale = "$($Hardware.RAM_GB)ГБ RAM + $($Hardware.VRAM_GB)ГБ VRAM — средний тир с GPU"
            ExpectedTime = "10-25 сек"
            DownloadSize = "3 ГБ"
        }
    }
    if ($Hardware.RAM_GB -ge 8) {
        return [PSCustomObject]@{
            Tier = "recommended"
            Model = "qwen3:1.7b"
            Rationale = "$($Hardware.RAM_GB)ГБ RAM, CPU-only вариант достаточен"
            ExpectedTime = "20-40 сек CPU"
            DownloadSize = "1.5 ГБ"
        }
    }
    return [PSCustomObject]@{
        Tier = "lite"
        Model = "qwen3:0.6b"
        Rationale = "$($Hardware.RAM_GB)ГБ RAM — лёгкая модель, рецензент будет слабее"
        ExpectedTime = "10-20 сек CPU"
        DownloadSize = "600 МБ"
    }
}
```

- [ ] **Step 2: Test on local machine**

```powershell
. .\scripts\lib\hardware_detect.ps1
$hw = Get-SystemHardware
$hw | Format-List
Recommend-ModelTier -Hardware $hw | Format-List
```

Expected: видим разумные значения RAM/VRAM/CPU, tier-рекомендацию.

- [ ] **Step 3: Commit**

```bash
git add scripts/lib/hardware_detect.ps1
git commit -m "feat(installer): hardware detection + model tier recommendation

Get-SystemHardware returns RAM/CPU/GPU/VRAM, attempts nvidia-smi for
accurate VRAM on NVIDIA cards (AdapterRAM is 32-bit, wrong for 4+GB).
Recommend-ModelTier maps to qwen3:0.6b / 1.7b / 4b / 8b with rationale.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Ollama Install Wizard

**Files:**
- Create: `scripts/install_ollama_wizard.ps1`

- [ ] **Step 1: Main wizard script**

```powershell
# scripts/install_ollama_wizard.ps1
# Interactive wizard: detect hardware, recommend model, install Ollama + model, canary test

param(
    [string]$ModelOverride = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
. (Join-Path $ScriptDir "lib\hardware_detect.ps1")

Write-Host ""
Write-Host "=== Мастер установки Ollama для Тезис ===" -ForegroundColor Cyan
Write-Host ""

# 1. Detect hardware
Write-Host "Определение конфигурации..." -ForegroundColor Yellow
$hw = Get-SystemHardware
Write-Host "  RAM:   $($hw.RAM_GB) ГБ"
Write-Host "  CPU:   $($hw.CPU_Name) ($($hw.CPU_Cores) ядер)"
Write-Host "  GPU:   $($hw.GPU_Name) ($($hw.VRAM_GB) ГБ VRAM)"
Write-Host ""

# 2. Recommend tier
$recommendation = Recommend-ModelTier -Hardware $hw
Write-Host "Рекомендую модель: " -NoNewline
Write-Host $recommendation.Model -ForegroundColor Green
Write-Host "  Обоснование: $($recommendation.Rationale)"
Write-Host "  Ожидаемое время рецензии: $($recommendation.ExpectedTime)"
Write-Host "  Размер скачивания: $($recommendation.DownloadSize)"
Write-Host ""

# 3. User confirmation
if ($ModelOverride) {
    $model = $ModelOverride
    Write-Host "Override: использовать $model" -ForegroundColor Yellow
} else {
    Write-Host "Опции:"
    Write-Host "  [Enter] — использовать рекомендуемую модель"
    Write-Host "  1 — qwen3:0.6b (лёгкая, слабее)"
    Write-Host "  2 — qwen3:1.7b (стандарт)"
    Write-Host "  3 — qwen3:4b (продвинутая)"
    Write-Host "  4 — qwen3:8b (полная)"
    Write-Host "  Q — выйти"
    Write-Host ""
    $choice = Read-Host "Ваш выбор"
    $model = switch ($choice.ToLower()) {
        "" { $recommendation.Model }
        "1" { "qwen3:0.6b" }
        "2" { "qwen3:1.7b" }
        "3" { "qwen3:4b" }
        "4" { "qwen3:8b" }
        "q" { exit 0 }
        default { $recommendation.Model }
    }
}

# 4. Check if Ollama is installed
Write-Host ""
Write-Host "Проверка Ollama..." -ForegroundColor Yellow
$ollamaExe = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaExe) {
    Write-Host "  Ollama не найдена. Устанавливаем..." -ForegroundColor Yellow
    $installerUrl = "https://ollama.com/download/OllamaSetup.exe"
    $installerPath = Join-Path $env:TEMP "OllamaSetup.exe"

    Write-Host "  Скачивание $installerUrl..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing

    Write-Host "  Запуск установщика (может запросить подтверждение UAC)..." -ForegroundColor Yellow
    # Ollama Windows installer uses Inno Setup — /VERYSILENT /SUPPRESSMSGBOXES
    $process = Start-Process -FilePath $installerPath -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART" -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        Write-Host "  ⚠ Тихий режим не сработал. Открываем GUI-установщик..." -ForegroundColor Yellow
        Start-Process -FilePath $installerPath -Wait
    }

    # Refresh PATH и проверка
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    $ollamaExe = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollamaExe) {
        Write-Host "  ❌ Не удалось обнаружить ollama после установки. Перезапустите терминал и повторите." -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ Ollama установлена" -ForegroundColor Green
} else {
    Write-Host "  ✓ Ollama уже установлена ($($ollamaExe.Source))" -ForegroundColor Green
}

# 5. Wait for Ollama daemon
Write-Host ""
Write-Host "Ожидание Ollama daemon..." -ForegroundColor Yellow
$timeout = 30
for ($i = 0; $i -lt $timeout; $i++) {
    try {
        $ping = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop
        Write-Host "  ✓ Daemon отвечает" -ForegroundColor Green
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

# 6. Check if model already pulled
Write-Host ""
Write-Host "Проверка модели $model..." -ForegroundColor Yellow
$tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags"
$hasModel = $tags.models | Where-Object { $_.name -eq $model }

if (-not $hasModel) {
    Write-Host "  Скачивание $model... (может занять 5-30 минут в зависимости от скорости)" -ForegroundColor Yellow
    & ollama pull $model
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ ollama pull завершился с ошибкой" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ Модель скачана" -ForegroundColor Green
} else {
    Write-Host "  ✓ Модель $model уже доступна" -ForegroundColor Green
}

# 7. Canary test
Write-Host ""
Write-Host "Тестовый запрос к рецензенту..." -ForegroundColor Yellow
$canaryPrompt = @"
Ответь коротким JSON-объектом формата {"status": "ok", "model": "название модели"}. Ничего больше.
"@

$response = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body (@{
    model = $model
    prompt = $canaryPrompt
    stream = $false
    format = "json"
} | ConvertTo-Json) -ContentType "application/json"

try {
    $parsed = $response.response | ConvertFrom-Json
    if ($parsed.status -eq "ok") {
        Write-Host "  ✓ Модель отвечает валидным JSON" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ JSON валиден, но содержимое неожиданное: $($response.response)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠ Ответ не парсится как JSON: $($response.response)" -ForegroundColor Yellow
    Write-Host "    Это не критично — Тезис всё равно работает, но рецензент может быть менее точным"
}

# 8. Save choice to app settings
$settingsPath = Join-Path $PSScriptRoot "..\app_data\settings.json"
if (-not (Test-Path (Split-Path $settingsPath -Parent))) {
    New-Item -Path (Split-Path $settingsPath -Parent) -ItemType Directory -Force | Out-Null
}

$settings = @{
    ollama = @{
        endpoint = "http://localhost:11434"
        model = $model
        tier = $recommendation.Tier
    }
}
$settings | ConvertTo-Json -Depth 5 | Set-Content -Path $settingsPath -Encoding UTF8
Write-Host ""
Write-Host "Настройки сохранены в $settingsPath" -ForegroundColor Green

Write-Host ""
Write-Host "=== Готово ===" -ForegroundColor Cyan
Write-Host "Теперь можно запускать Tezis.exe" -ForegroundColor Green
```

- [ ] **Step 2: Manual test**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_ollama_wizard.ps1
```

Проверить на локальной машине — проходит все этапы, canary выдаёт json.

- [ ] **Step 3: Commit**

```bash
git add scripts/install_ollama_wizard.ps1
git commit -m "feat(installer): interactive Ollama wizard with tiered recommendations

Full flow: detect hardware → recommend tier → user confirms/overrides →
install Ollama if needed (with /VERYSILENT fallback to GUI) → pull
model with progress → canary JSON test → persist choice to settings.json.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Flet Pack Build Script

**Files:**
- Create: `scripts/build_flet_exe.ps1`

- [ ] **Step 1: Build script**

```powershell
# scripts/build_flet_exe.ps1
# Build Tezis.exe via flet pack

param(
    [string]$SeedDatabasePath = "build\demo_seed\state_exam_public_admin_demo_v2.db",
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Сборка Tezis.exe ===" -ForegroundColor Cyan

# 1. Ensure seed exists
if (-not (Test-Path $SeedDatabasePath)) {
    Write-Host "❌ Seed DB не найдена: $SeedDatabasePath" -ForegroundColor Red
    Write-Host "   Собери её через: python scripts/build_state_exam_seed.py ..." -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ Seed DB: $SeedDatabasePath"

# 2. Run tests before build
Write-Host ""
Write-Host "Прогоняем тесты..." -ForegroundColor Yellow
pytest -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Тесты упали, собирать не буду" -ForegroundColor Red
    exit 1
}

# 3. Clean dist
Write-Host ""
Write-Host "Очистка $OutputDir..." -ForegroundColor Yellow
if (Test-Path $OutputDir) {
    Remove-Item -Path $OutputDir -Recurse -Force
}
New-Item -Path $OutputDir -ItemType Directory | Out-Null

# 4. flet pack
Write-Host ""
Write-Host "Запуск flet pack..." -ForegroundColor Yellow
$env:TEZIS_SEED_DATABASE = (Resolve-Path $SeedDatabasePath).Path

flet pack `
    ui_flet\main.py `
    --name "Tezis" `
    --add-data "$SeedDatabasePath;data" `
    --add-data "ui_flet\theme\fonts;ui_flet\theme\fonts" `
    --distpath "$OutputDir" `
    --workpath "$OutputDir\build" `
    --icon "assets\icon.ico"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ flet pack упал" -ForegroundColor Red
    exit 1
}

# 5. Verify exe exists
$exe = Join-Path $OutputDir "Tezis.exe"
if (-not (Test-Path $exe)) {
    Write-Host "❌ Не нашёл $exe после сборки" -ForegroundColor Red
    exit 1
}

$size_mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "✓ Сборка успешна: $exe ($size_mb МБ)" -ForegroundColor Green
```

- [ ] **Step 2: Smoke build (может упасть до W2 merge)**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_flet_exe.ps1
```

Если W2 ещё не мерджится — создать placeholder `ui_flet/main.py` с минимальным Flet-окном для проверки самого flet pack.

- [ ] **Step 3: Commit**

```bash
git add scripts/build_flet_exe.ps1
git commit -m "feat(installer): flet pack build script with seed DB bundling

Validates seed exists, runs pytest, cleans dist, invokes flet pack
with --add-data for seed and fonts, reports size. Icon from
assets/icon.ico.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Package Release Script

**Files:**
- Create: `scripts/package_release.ps1`
- Create: `scripts/release_template/README.txt` — для однокурсников

- [ ] **Step 1: README для однокурсников**

Создать `scripts/release_template/README.txt`:

```
===============================================================
  ТЕЗИС — тренажёр для подготовки к письменному госэкзамену
  Версия 2.0
===============================================================

Как начать:

1. Распакуйте архив куда угодно (рабочий стол или Documents).

2. Запустите install_ollama_wizard.ps1:
   Правой кнопкой → «Запустить с помощью PowerShell»
   (Если Windows ругается — нажмите «Всё равно открыть»)
   Мастер сам подберёт модель под ваш компьютер, скачает её и настроит.
   Займёт 5-30 минут в зависимости от скорости интернета.

3. Запустите Tezis.exe.

4. В приложении нажмите «Тренировка» → выберите режим
   «Рецензия» или «Письменный госэкзамен» → выберите билет.
   Напишите полный ответ, нажмите «Получить рецензию».
   Рецензент проверит ваш ответ по тезисам.

Что делать, если:

• «Ollama не отвечает»
  Откройте «Службы» (services.msc), найдите «Ollama», запустите.

• Рецензент отвечает медленно
  Это нормально на слабом железе (CPU вместо GPU). Ожидайте 30-60 сек.

• Рецензент выдаёт непонятный ответ
  Возможно, модель слишком маленькая. Запустите install_ollama_wizard.ps1
  ещё раз и выберите модель побольше.

• Нужна помощь
  Напишите [вашему имени/контакту].

Удачи на экзамене!
```

- [ ] **Step 2: Package script**

Создать `scripts/package_release.ps1`:

```powershell
# scripts/package_release.ps1
# Create distributable zip: exe + wizard + seed + README

param(
    [string]$Version = "2.0.0",
    [string]$OutputZip = "dist\Tezis-v$Version-windows.zip"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Упаковка релиза v$Version ===" -ForegroundColor Cyan

# 1. Ensure build exists
$exe = "dist\Tezis.exe"
if (-not (Test-Path $exe)) {
    Write-Host "❌ Сначала запусти build_flet_exe.ps1" -ForegroundColor Red
    exit 1
}

# 2. Build staging dir
$stagingDir = "dist\staging\Tezis-v$Version"
if (Test-Path $stagingDir) {
    Remove-Item -Path $stagingDir -Recurse -Force
}
New-Item -Path $stagingDir -ItemType Directory -Force | Out-Null
New-Item -Path "$stagingDir\scripts" -ItemType Directory -Force | Out-Null
New-Item -Path "$stagingDir\data" -ItemType Directory -Force | Out-Null

# 3. Copy files
Copy-Item -Path $exe -Destination $stagingDir
Copy-Item -Path "scripts\install_ollama_wizard.ps1" -Destination "$stagingDir\scripts\"
Copy-Item -Path "scripts\lib\hardware_detect.ps1" -Destination "$stagingDir\scripts\"
Copy-Item -Path "scripts\check_ollama.ps1" -Destination "$stagingDir\scripts\" -ErrorAction SilentlyContinue
Copy-Item -Path "build\demo_seed\state_exam_public_admin_demo_v2.db" -Destination "$stagingDir\data\"
Copy-Item -Path "scripts\release_template\README.txt" -Destination $stagingDir
Copy-Item -Path "LICENSE" -Destination "$stagingDir\LICENSE.txt" -ErrorAction SilentlyContinue

# 4. Create zip
if (Test-Path $OutputZip) {
    Remove-Item -Path $OutputZip -Force
}
Compress-Archive -Path $stagingDir -DestinationPath $OutputZip -CompressionLevel Optimal

$size_mb = [math]::Round((Get-Item $OutputZip).Length / 1MB, 1)
Write-Host ""
Write-Host "✓ Релиз готов: $OutputZip ($size_mb МБ)" -ForegroundColor Green
```

- [ ] **Step 3: Commit**

```bash
git add scripts/package_release.ps1 scripts/release_template/
git commit -m "feat(installer): package release zip + README for classmates

Zip structure: Tezis.exe + scripts/install_ollama_wizard.ps1 +
data/seed.db + README.txt. README covers install, troubleshooting,
what to do if Ollama misbehaves.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: VM Smoke Test

**Goal:** Протестировать pipeline на чистой Windows VM (без Python, без Ollama, без venv). Это критический тест — то, что увидят однокурсники.

**Files:**
- Create: `docs/superpowers/smoke-reports/2026-04-18-vm-smoke.md` — отчёт

- [ ] **Step 1: Подготовить VM**

Варианты:
- Hyper-V/VirtualBox с Windows 10 / 11 install
- Windows Sandbox (встроенная) — быстрее
- Реальная чужая машина, если доступна

Предварительное условие: не установлено Python, Ollama, Git.

- [ ] **Step 2: Скопировать zip, распаковать**

- Ручная распаковка zip в `Downloads/Tezis/`

- [ ] **Step 3: Запустить wizard**

```powershell
cd Tezis-v2.0
powershell -ExecutionPolicy Bypass -File scripts\install_ollama_wizard.ps1
```

Проверить:
- Детект железа корректный
- Рекомендация tier разумная
- Ollama скачивается и устанавливается
- Модель pull-ится с прогрессом
- Canary test проходит
- settings.json записан

- [ ] **Step 4: Запустить Tezis.exe**

Проверить:
- Окно открывается
- Sidebar работает, все 6 routes
- Library загружает документы из seed
- Tickets показывает билеты
- Training → выбрать билет → Review workspace
- Написать короткий ответ → submit → получить рецензию (может быть 30-60 сек)
- Theme toggle работает
- Resize окна — layout реагирует

- [ ] **Step 5: Написать отчёт**

Создать `docs/superpowers/smoke-reports/2026-04-18-vm-smoke.md`:

```markdown
# VM Smoke Report — Tezis v2.0 Windows

**Date:** 2026-04-XX
**VM:** Windows 10/11 (clean install)
**RAM:** X GB
**CPU:** Y cores
**GPU:** Z / integrated

## Step-by-step

### 1. Unzip and navigate
- [ok / fail] ...

### 2. install_ollama_wizard.ps1
- Hardware detection: [ok / wrong]
- Recommended tier: [X]
- User override (if tested): [X]
- Ollama install: [ok / fail — lines from log]
- Model pull: [ok / fail]
- Canary test: [ok / fail]

### 3. Tezis.exe
- Opens: [ok / fail]
- Navigation: [all 6 / which failed]
- Theme toggle: [ok / fail]
- Training → Review: [ok / fail + timing]

## Issues found

1. ...

## Verdict

[Ship-ready / needs-fixes-list]
```

- [ ] **Step 6: Commit отчёт**

```bash
git add docs/superpowers/smoke-reports/2026-04-18-vm-smoke.md
git commit -m "docs(smoke): VM smoke report for Tezis v2.0 Windows

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: macOS Mirror (Optional, lower priority)

Если время остаётся, аналогичный `scripts/install_ollama_macos.sh` с `sysctl hw.memsize`, `system_profiler SPDisplaysDataType`. `flet pack` на Mac требует другого icon формата (.icns). Можно пропустить для v2.0 и оставить на v2.1.

---

## Task 7: Merge to main

**⚠️ Coordinator task.**

После W1 merged (seed v2 доступна), W3 merged перед W2 чтобы build scripts работали:

```bash
cd D:\ticket-exam-trainer
git merge --no-ff installer -m "Merge W3 installer: Ollama wizard + flet pack + release package"
pytest -q
git push origin main
```

---

## Acceptance Criteria (W3)

1. ✅ `scripts\install_ollama_wizard.ps1` проходит на чистой VM (hardware detect → model install → canary)
2. ✅ `scripts\build_flet_exe.ps1` собирает `dist\Tezis.exe` без ошибок, размер ≤ 150 МБ
3. ✅ `scripts\package_release.ps1` создаёт `dist\Tezis-v2.0-windows.zip` размером ≤ 200 МБ
4. ✅ VM smoke test (Task 5) задокументирован в `docs/superpowers/smoke-reports/`
5. ✅ Однокурсник может повторить шаги из README.txt и получить работающий рецензент
