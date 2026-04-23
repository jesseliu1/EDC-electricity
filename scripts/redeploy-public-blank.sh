#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

sync_script="$repo_root/scripts/sync-edc-server.sh"
publish_script="$repo_root/scripts/publish-edc-web-and-asns.sh"

runtime_dir="${EDC_SERVER_RUNTIME_DIR:-/home/openclaw/edc-electricity-server}"
runtime_db="${EDC_SERVER_RUNTIME_DB:-$runtime_dir/data/asns.db}"
service_name="${EDC_BACKEND_SERVICE_NAME:-edc-backend.service}"
health_url="${EDC_BACKEND_HEALTH_URL:-http://127.0.0.1:8001/health}"
service_dropin_dir="${EDC_BACKEND_SERVICE_DROPIN_DIR:-$HOME/.config/systemd/user/$service_name.d}"
blank_dropin_file="$service_dropin_dir/blank-bootstrap.conf"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$runtime_dir/backups/${timestamp}-factory-reset"

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

ensure_user_systemd_bus() {
  local uid runtime_dir bus_socket

  uid="$(id -u)"
  runtime_dir="/run/user/$uid"
  bus_socket="$runtime_dir/bus"

  if [[ -z "${XDG_RUNTIME_DIR:-}" ]]; then
    export XDG_RUNTIME_DIR="$runtime_dir"
  fi
  if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$bus_socket"
  fi

  if [[ ! -S "$bus_socket" ]]; then
    echo "systemd user bus socket not found: $bus_socket" >&2
    exit 1
  fi
}

wait_for_health() {
  local attempts="${1:-15}"
  local delay_seconds="${2:-1}"
  local attempt=1

  while (( attempt <= attempts )); do
    if curl --fail --silent --show-error "$health_url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay_seconds"
    attempt=$((attempt + 1))
  done

  curl --fail --silent --show-error "$health_url" >/dev/null
}

backup_existing_db() {
  mkdir -p "$backup_dir"

  if [[ -e "$runtime_db" ]]; then
    cp -a "$runtime_db" "$backup_dir/asns.db.before-reset"
  fi
  if [[ -e "${runtime_db}-wal" ]]; then
    cp -a "${runtime_db}-wal" "$backup_dir/asns.db-wal.before-reset"
  fi
  if [[ -e "${runtime_db}-shm" ]]; then
    cp -a "${runtime_db}-shm" "$backup_dir/asns.db-shm.before-reset"
  fi
  if [[ -e "${runtime_db}-journal" ]]; then
    cp -a "${runtime_db}-journal" "$backup_dir/asns.db-journal.before-reset"
  fi
}

ensure_blank_bootstrap_dropin() {
  mkdir -p "$service_dropin_dir"
  cat >"$blank_dropin_file" <<'EOF'
[Service]
Environment=ASNS_BOOTSTRAP_MODE=blank
EOF
  systemctl --user daemon-reload
}

assert_factory_reset_blank_db() {
  local python_bin="$runtime_dir/venv/bin/python"

  RUNTIME_DB_PATH="$runtime_db" "$python_bin" - <<'PY'
import json
import os
import sqlite3
from pathlib import Path

db_path = Path(os.environ["RUNTIME_DB_PATH"])
connection = sqlite3.connect(db_path)
connection.row_factory = sqlite3.Row
try:
    tables = [
        "baseline_definitions",
        "baseline_definition_metrics",
        "baselines",
        "heats",
        "metric_series",
        "tasks",
    ]
    counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }

    rows = {
        row["key"]: row["value"]
        for row in connection.execute(
            "SELECT key, value FROM settings WHERE key IN ('runtime_baseline_definitions', 'runtime_baselines', 'runtime_settings_store')"
        )
    }

    definition_payload = json.loads(rows.get("runtime_baseline_definitions") or "{}")
    baseline_payload = json.loads(rows.get("runtime_baselines") or "{}")
    settings_payload = json.loads(rows.get("runtime_settings_store") or "{}")
    active_baseline = settings_payload.get("active_baseline_id")

    active_baseline_id = ""
    if isinstance(active_baseline, dict):
        active_baseline_id = str(active_baseline.get("value") or "").strip()
    elif isinstance(active_baseline, str):
        active_baseline_id = active_baseline.strip()

    non_blank_tables = {table: count for table, count in counts.items() if count != 0}
    if non_blank_tables:
        raise SystemExit(f"factory-reset left business tables non-empty: {non_blank_tables}")
    if definition_payload:
        raise SystemExit("runtime_baseline_definitions is not blank after factory-reset")
    if baseline_payload:
        raise SystemExit("runtime_baselines is not blank after factory-reset")
    if active_baseline_id:
        raise SystemExit(f"active_baseline_id is not blank after factory-reset: {active_baseline_id}")
finally:
    connection.close()
PY
}

require_command curl
require_command cp
require_command mkdir
require_command systemctl
ensure_user_systemd_bus

if [[ ! -x "$sync_script" ]]; then
  echo "Sync script not found or not executable: $sync_script" >&2
  exit 1
fi

if [[ ! -x "$publish_script" ]]; then
  echo "Publish script not found or not executable: $publish_script" >&2
  exit 1
fi

log_step "Syncing runtime without source refresh and without backend autostart"
(
  export EDC_SERVER_SKIP_SOURCE_REFRESH="${EDC_SERVER_SKIP_SOURCE_REFRESH:-1}"
  export EDC_SERVER_SKIP_START=1
  "$sync_script"
)

log_step "Stopping $service_name before factory-reset"
systemctl --user stop "$service_name"

log_step "Backing up current runtime database files"
backup_existing_db

log_step "Ensuring blank bootstrap drop-in"
ensure_blank_bootstrap_dropin

log_step "Factory-resetting runtime database"
"$runtime_dir/venv/bin/python" -m src.runtime_state_admin \
  --db "$runtime_db" \
  --mode factory-reset

log_step "Verifying reset database is blank"
assert_factory_reset_blank_db

log_step "Starting $service_name in blank mode"
systemctl --user start "$service_name"

log_step "Checking backend health"
wait_for_health 15 1

log_step "Publishing EDC web and ASNS host"
"$publish_script"

printf "\nBlank redeploy complete.\n"
printf "DB backup directory: %s\n" "$backup_dir"
printf "Blank drop-in: %s\n" "$blank_dropin_file"
