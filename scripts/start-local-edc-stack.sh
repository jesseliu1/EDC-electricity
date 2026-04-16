#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

server_dir="$repo_root/apps/server"
web_dir="$repo_root/apps/web"
asns_dir="$repo_root/docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統"
run_dir="$repo_root/.tmp_run/local"
db_path="$server_dir/data/asns.db"

server_dir_win="$(cygpath -w "$server_dir")"
web_dir_win="$(cygpath -w "$web_dir")"
asns_dir_win="$(cygpath -w "$asns_dir")"
run_dir_win="$(cygpath -w "$run_dir")"
db_path_win="$(cygpath -w "$db_path")"

backend_log="$run_dir/backend.log"
backend_err_log="$run_dir/backend.err.log"
web_log="$run_dir/web.log"
web_err_log="$run_dir/web.err.log"
asns_log="$run_dir/asns.log"
asns_err_log="$run_dir/asns.err.log"

backend_log_win="$(cygpath -w "$backend_log")"
backend_err_log_win="$(cygpath -w "$backend_err_log")"
web_log_win="$(cygpath -w "$web_log")"
web_err_log_win="$(cygpath -w "$web_err_log")"
asns_log_win="$(cygpath -w "$asns_log")"
asns_err_log_win="$(cygpath -w "$asns_err_log")"

require_command() {
  local command_name="$1"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
}

log_step() {
  printf "\n==> %s\n" "$1"
}

wait_for_url() {
  local url="$1"
  local attempts="${2:-20}"
  local delay_seconds="${3:-1}"
  local attempt=1

  while (( attempt <= attempts )); do
    if curl --fail --silent --show-error --location --max-time 20 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay_seconds"
    attempt=$((attempt + 1))
  done

  curl --fail --silent --show-error --location --max-time 20 "$url" >/dev/null
}

assert_contains() {
  local url="$1"
  local expected="$2"

  if ! curl --silent --show-error --location --max-time 20 "$url" | grep -Fq "$expected"; then
    echo "Expected response from $url to contain: $expected" >&2
    exit 1
  fi
}

assert_blank_runtime_state() {
  powershell.exe -NoProfile -Command "
    \$serverDir = '$server_dir_win'
    \$python = Join-Path \$serverDir '.venv\\Scripts\\python.exe'
    \$script = @'
import json
import sqlite3
from pathlib import Path

db_path = Path(r'$db_path_win')
connection = sqlite3.connect(db_path)
connection.row_factory = sqlite3.Row
try:
    rows = {
        row['key']: row['value']
        for row in connection.execute(
            \"select key, value from settings where key in ('runtime_baseline_definitions', 'runtime_baselines', 'runtime_settings_store')\"
        )
    }

    definition_payload = json.loads(rows.get('runtime_baseline_definitions') or '{}')
    baseline_payload = json.loads(rows.get('runtime_baselines') or '{}')
    settings_payload = json.loads(rows.get('runtime_settings_store') or '{}')
    active_baseline_id = ''
    active_baseline = settings_payload.get('active_baseline_id')
    if isinstance(active_baseline, dict):
        active_baseline_id = str(active_baseline.get('value') or '').strip()

    if definition_payload:
        raise SystemExit(f'runtime_baseline_definitions is not blank: {list(definition_payload.keys())}')
    if baseline_payload:
        raise SystemExit(f'runtime_baselines is not blank: {list(baseline_payload.keys())}')
    if active_baseline_id:
        raise SystemExit(f'active_baseline_id is not blank: {active_baseline_id}')
finally:
    connection.close()
'@
    \$tmp = Join-Path \$env:TEMP 'edc-assert-blank-runtime.py'
    Set-Content -LiteralPath \$tmp -Value \$script -Encoding UTF8
    try {
      & \$python \$tmp
      if (\$LASTEXITCODE -ne 0) {
        exit \$LASTEXITCODE
      }
    } finally {
      Remove-Item -LiteralPath \$tmp -Force -ErrorAction SilentlyContinue
    }
  "
}

stop_listener() {
  local port="$1"

  powershell.exe -NoProfile -Command "
    \$ErrorActionPreference = 'SilentlyContinue'
    \$listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
    if (\$listener) {
      Stop-Process -Id \$listener.OwningProcess -Force
    }
    exit 0
  " >/dev/null
}

factory_reset_runtime_state() {
  powershell.exe -NoProfile -Command "
    \$serverDir = '$server_dir_win'
    \$python = Join-Path \$serverDir '.venv\\Scripts\\python.exe'
    if (-not (Test-Path \$python)) {
      throw 'Backend Python not found'
    }
    & \$python -m src.runtime_state_admin --db '$db_path_win' --mode factory-reset
    if (\$LASTEXITCODE -ne 0) {
      exit \$LASTEXITCODE
    }
  "
}

start_backend() {
  powershell.exe -NoProfile -Command "
    \$serverDir = '$server_dir_win'
    \$python = Join-Path \$serverDir '.venv\\Scripts\\python.exe'
    \$env:ASNS_BOOTSTRAP_MODE = 'blank'
    Start-Process -FilePath \$python -ArgumentList '-m','uvicorn','src.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory \$serverDir -RedirectStandardOutput '$backend_log_win' -RedirectStandardError '$backend_err_log_win'
  " >/dev/null
}

start_web() {
  powershell.exe -NoProfile -Command "
    Start-Process -FilePath 'pnpm.cmd' -ArgumentList 'dev','--','--host','0.0.0.0' -WorkingDirectory '$web_dir_win' -RedirectStandardOutput '$web_log_win' -RedirectStandardError '$web_err_log_win'
  " >/dev/null
}

start_asns() {
  powershell.exe -NoProfile -Command "
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','set PORT=3001&& set ASNS_BASE_PATH=/&& set ASNS_EDC_API_PORT=8000&& set ASNS_EDC_API_HOST=127.0.0.1&& set ASNS_EDC_APP_URL=http://localhost:3000/edc/&& node server.mjs' -WorkingDirectory '$asns_dir_win' -RedirectStandardOutput '$asns_log_win' -RedirectStandardError '$asns_err_log_win'
  " >/dev/null
}

require_command powershell.exe
require_command cmd.exe
require_command npm
require_command pnpm
require_command curl
require_command cygpath

if [[ ! -d "$server_dir" ]]; then
  echo "Server directory not found: $server_dir" >&2
  exit 1
fi

if [[ ! -d "$web_dir" ]]; then
  echo "Web directory not found: $web_dir" >&2
  exit 1
fi

if [[ ! -d "$asns_dir" ]]; then
  echo "ASNS directory not found: $asns_dir" >&2
  exit 1
fi

mkdir -p "$run_dir"

log_step "Stopping existing local listeners on 8000 / 3000 / 3001"
stop_listener 8000
stop_listener 3000
stop_listener 3001

rm -f "$backend_log" "$backend_err_log" "$web_log" "$web_err_log" "$asns_log" "$asns_err_log"

log_step "Factory-resetting local runtime state before startup"
factory_reset_runtime_state

log_step "Building ASNS host before starting 3001"
(
  cd "$asns_dir"
  npm run build
)

log_step "Starting backend on http://127.0.0.1:8000"
start_backend
wait_for_url "http://127.0.0.1:8000/health" 20 1
assert_blank_runtime_state

log_step "Starting EDC web on http://localhost:3000/edc/"
start_web
wait_for_url "http://localhost:3000/edc/" 30 1
wait_for_url "http://localhost:3000/api/health" 20 1

log_step "Starting ASNS host on http://localhost:3001/"
start_asns
wait_for_url "http://localhost:3001/" 20 1
wait_for_url "http://localhost:3001/api/health" 20 1
assert_contains "http://localhost:3001/" 'window.__ASNS_EDC_APP_URL__ = "http://localhost:3000/edc/";'

printf "\nLocal stack is ready.\n"
printf "EDC web:     http://localhost:3000/edc/\n"
printf "ASNS host:   http://localhost:3001/\n"
printf "Backend API: http://127.0.0.1:8000\n"
printf "\nLogs:\n"
printf "  backend: %s\n" "$backend_log"
printf "  web:     %s\n" "$web_log"
printf "  asns:    %s\n" "$asns_log"
