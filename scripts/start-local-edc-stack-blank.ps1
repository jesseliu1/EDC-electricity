#requires -Version 7.0
<#
.SYNOPSIS
按“删库 + blank 重建”口径启动本机联调栈。

.DESCRIPTION
本脚本会：
1. 停止本机 8000 / 3000 / 3001 旧监听进程
2. 对 apps/server/data/asns.db 执行 factory-reset
3. 以 ASNS_BOOTSTRAP_MODE=blank 启动后端
4. 重新启动 Vite 前端与 ASNS 宿主
5. 校验空库、blank runtime 与宿主页 runtime 注入

本脚本不会：
- 保留现有 SQLite 业务数据
- 沿用当前 runtime / heats / baselines

如果你需要“保留现有 DB 继续联调”，请改用：
scripts/start-local-edc-stack-preserve-db.ps1
#>

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

$serverDir = Join-Path $repoRoot 'apps\server'
$webDir = Join-Path $repoRoot 'apps\web'
$refDir = Join-Path $repoRoot 'docs\Ref'
$asnsDir = (
    Get-ChildItem -LiteralPath $refDir |
    Where-Object { $_.PSIsContainer -and $_.Name -like 'asns*' } |
    Select-Object -First 1 -ExpandProperty FullName
)
$runDir = Join-Path $repoRoot '.tmp_run\local'
$dbPath = Join-Path $serverDir 'data\asns.db'

$backendLog = Join-Path $runDir 'backend.log'
$backendErrLog = Join-Path $runDir 'backend.err.log'
$webLog = Join-Path $runDir 'web.log'
$webErrLog = Join-Path $runDir 'web.err.log'
$asnsLog = Join-Path $runDir 'asns.log'
$asnsErrLog = Join-Path $runDir 'asns.err.log'

$python = Join-Path $serverDir '.venv\Scripts\python.exe'
$npmCmd = 'npm.cmd'
$pnpmCmd = 'pnpm.cmd'

function Require-Command {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

function Write-Step {
    param([Parameter(Mandatory = $true)][string]$Message)

    Write-Host ''
    Write-Host "==> $Message"
}

function Stop-Listener {
    param([Parameter(Mandatory = $true)][int]$Port)

    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

function Wait-ForUrl {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$Attempts = 30,
        [int]$DelaySeconds = 1
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt += 1) {
        try {
            & curl.exe --fail --silent --show-error --location --max-time 20 $Url | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return
            }
        } catch {
        }
        Start-Sleep -Seconds $DelaySeconds
    }

    & curl.exe --fail --silent --show-error --location --max-time 20 $Url | Out-Null
}

function Assert-Contains {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Expected
    )

    $response = & curl.exe --silent --show-error --location --max-time 20 $Url
    if ($LASTEXITCODE -ne 0 -or -not $response.Contains($Expected)) {
        throw "Expected response from $Url to contain: $Expected"
    }
}

function Assert-BlankRuntimeState {
    param([Parameter(Mandatory = $true)][string]$DbFile)

    $pythonCode = @"
import json
import sqlite3
from pathlib import Path

db_path = Path(r'$DbFile')
connection = sqlite3.connect(db_path)
connection.row_factory = sqlite3.Row
try:
    tables = [
        'baseline_definitions',
        'baseline_definition_metrics',
        'baselines',
        'heats',
        'metric_series',
        'tasks',
    ]
    counts = {
        table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        for table in tables
    }

    rows = {
        row['key']: row['value']
        for row in connection.execute(
            "select key, value from settings where key in ('runtime_baseline_definitions', 'runtime_baselines', 'runtime_settings_store')"
        )
    }

    definition_payload = json.loads(rows.get('runtime_baseline_definitions') or '{}')
    baseline_payload = json.loads(rows.get('runtime_baselines') or '{}')
    settings_payload = json.loads(rows.get('runtime_settings_store') or '{}')
    active_baseline_id = ''
    active_baseline = settings_payload.get('active_baseline_id')
    if isinstance(active_baseline, dict):
        active_baseline_id = str(active_baseline.get('value') or '').strip()

    for table, count in counts.items():
        print(f'{table}={count}')
        if count != 0:
            raise SystemExit(f'{table} is not blank: {count}')

    if definition_payload:
        raise SystemExit(f'runtime_baseline_definitions is not blank: {list(definition_payload.keys())}')
    if baseline_payload:
        raise SystemExit(f'runtime_baselines is not blank: {list(baseline_payload.keys())}')
    if active_baseline_id:
        raise SystemExit(f'active_baseline_id is not blank: {active_baseline_id}')
finally:
    connection.close()
"@

    $tmpScript = Join-Path $env:TEMP 'edc-assert-blank-runtime.py'
    Set-Content -LiteralPath $tmpScript -Value $pythonCode -Encoding UTF8
    try {
        & $python $tmpScript
        if ($LASTEXITCODE -ne 0) {
            throw 'Blank runtime verification failed.'
        }
    } finally {
        Remove-Item -LiteralPath $tmpScript -Force -ErrorAction SilentlyContinue
    }
}

Require-Command 'curl.exe'
Require-Command $npmCmd
Require-Command $pnpmCmd
Require-Command 'node'
Require-Command 'cmd.exe'

if (-not (Test-Path -LiteralPath $serverDir)) {
    throw "Server directory not found: $serverDir"
}

if (-not (Test-Path -LiteralPath $webDir)) {
    throw "Web directory not found: $webDir"
}

if (-not $asnsDir -or -not (Test-Path -LiteralPath $asnsDir)) {
    throw 'ASNS directory not found under docs\Ref'
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend Python not found: $python"
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null
Remove-Item -LiteralPath $backendLog, $backendErrLog, $webLog, $webErrLog, $asnsLog, $asnsErrLog -Force -ErrorAction SilentlyContinue

Write-Step 'Stopping existing local listeners on 8000 / 3000 / 3001'
Stop-Listener 8000
Stop-Listener 3000
Stop-Listener 3001

Write-Step 'Factory-resetting local runtime state before startup'
& $python -m src.runtime_state_admin --db $dbPath --mode factory-reset
if ($LASTEXITCODE -ne 0) {
    throw 'Factory-reset failed.'
}

Write-Step 'Building ASNS host before starting 3001'
Push-Location $asnsDir
try {
    & $npmCmd run build
    if ($LASTEXITCODE -ne 0) {
        throw 'ASNS host build failed.'
    }
} finally {
    Pop-Location
}

Write-Step 'Starting backend on http://127.0.0.1:8000 (blank mode)'
Start-Process -FilePath 'cmd.exe' `
    -ArgumentList @(
        '/c',
        "set ASNS_BOOTSTRAP_MODE=blank&& `"$python`" -m uvicorn src.main:app --host 127.0.0.1 --port 8000"
    ) `
    -WorkingDirectory $serverDir `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrLog | Out-Null
Wait-ForUrl -Url 'http://127.0.0.1:8000/health' -Attempts 30 -DelaySeconds 1
Assert-BlankRuntimeState -DbFile $dbPath

Write-Step 'Starting EDC web on http://localhost:3000/edc/'
Start-Process -FilePath $pnpmCmd `
    -ArgumentList @('dev', '--', '--host', '0.0.0.0') `
    -WorkingDirectory $webDir `
    -RedirectStandardOutput $webLog `
    -RedirectStandardError $webErrLog | Out-Null
Wait-ForUrl -Url 'http://localhost:3000/edc/' -Attempts 40 -DelaySeconds 1
Wait-ForUrl -Url 'http://localhost:3000/api/health' -Attempts 30 -DelaySeconds 1

Write-Step 'Starting ASNS host on http://localhost:3001/'
Start-Process -FilePath 'cmd.exe' `
    -ArgumentList @(
        '/c',
        'set PORT=3001&& set ASNS_BASE_PATH=/&& set ASNS_EDC_API_PORT=8000&& set ASNS_EDC_API_HOST=127.0.0.1&& set ASNS_EDC_API_PROTOCOL=http&& set ASNS_EDC_APP_URL=http://localhost:3000/edc/&& node server.mjs'
    ) `
    -WorkingDirectory $asnsDir `
    -RedirectStandardOutput $asnsLog `
    -RedirectStandardError $asnsErrLog | Out-Null
Wait-ForUrl -Url 'http://localhost:3001/' -Attempts 30 -DelaySeconds 1
Wait-ForUrl -Url 'http://localhost:3001/api/health' -Attempts 30 -DelaySeconds 1
Assert-Contains -Url 'http://localhost:3001/' -Expected 'window.__ASNS_EDC_APP_URL__ = "http://localhost:3000/edc/";'

Write-Host ''
Write-Host 'Local stack is ready.'
Write-Host 'Blank mode: SQLite was factory-reset and rebuilt.'
Write-Host "EDC web:     http://localhost:3000/edc/"
Write-Host "ASNS host:   http://localhost:3001/"
Write-Host "Backend API: http://127.0.0.1:8000"
Write-Host ''
Write-Host 'Logs:'
Write-Host "  backend: $backendLog"
Write-Host "  web:     $webLog"
Write-Host "  asns:    $asnsLog"
