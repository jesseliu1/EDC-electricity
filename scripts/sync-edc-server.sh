#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

source_dir="${EDC_SERVER_SOURCE_DIR:-$repo_root/apps/server}"
runtime_dir="${EDC_SERVER_RUNTIME_DIR:-/home/openclaw/edc-electricity-server}"
service_name="${EDC_BACKEND_SERVICE_NAME:-edc-backend.service}"
health_url="${EDC_BACKEND_HEALTH_URL:-http://127.0.0.1:8001/health}"
python_bin="${EDC_BACKEND_PYTHON_BIN:-python3}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$runtime_dir/backups/$timestamp"

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
  local attempts="${1:-10}"
  local delay_seconds="${2:-1}"
  local attempt=1

  while (( attempt <= attempts )); do
    if curl --fail --silent "$health_url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay_seconds"
    attempt=$((attempt + 1))
  done

  curl --fail --silent --show-error "$health_url"
}

copy_if_exists() {
  local relative_path="$1"

  if [[ -e "$source_dir/$relative_path" ]]; then
    cp -a "$source_dir/$relative_path" "$runtime_dir/"
  fi
}

cleanup_runtime_root() {
  find "$runtime_dir" -maxdepth 1 -mindepth 1 \
    ! -name data \
    ! -name .logs \
    ! -name backups \
    -exec rm -rf {} +
}

rebuild_runtime_venv() {
  log_step "Rebuilding runtime virtualenv with $python_bin"
  "$python_bin" -m venv "$runtime_dir/venv"
  "$runtime_dir/venv/bin/pip" install --upgrade pip setuptools wheel
  "$runtime_dir/venv/bin/pip" install "$runtime_dir"
}

require_command tar
require_command find
require_command cp
require_command curl
require_command systemctl
require_command "$python_bin"
ensure_user_systemd_bus

if [[ ! -d "$source_dir" ]]; then
  echo "EDC server source directory not found: $source_dir" >&2
  exit 1
fi

mkdir -p "$runtime_dir" "$runtime_dir/backups" "$backup_dir"

log_step "Backing up current runtime tree"
tar -C "$(dirname "$runtime_dir")" -czf "$backup_dir/runtime-pre-sync.tgz" \
  --exclude="$(basename "$runtime_dir")/backups" \
  "$(basename "$runtime_dir")"

log_step "Stopping $service_name"
systemctl --user stop "$service_name"

log_step "Cleaning runtime tree while preserving data/, .logs/, backups/"
cleanup_runtime_root

log_step "Copying tracked server files into runtime copy"
copy_if_exists README.md
copy_if_exists alembic.ini
copy_if_exists pyproject.toml
copy_if_exists uv.lock
copy_if_exists alembic
copy_if_exists src
copy_if_exists tests

rebuild_runtime_venv

if [[ "${EDC_SERVER_SKIP_SOURCE_REFRESH:-0}" != "1" ]]; then
  log_step "Refreshing source-bound runtime state from current EDC config"
  (
    cd "$runtime_dir"
    if [[ "${EDC_SERVER_REBIND_DEFINITIONS:-1}" == "1" ]]; then
      ./venv/bin/python -m src.runtime_state_admin \
        --db "$runtime_dir/data/asns.db" \
        --mode deploy-refresh
    else
      ./venv/bin/python -m src.runtime_state_admin \
        --db "$runtime_dir/data/asns.db" \
        --mode deploy-refresh \
        --no-rebind-definitions
    fi
  )
fi

log_step "Compiling runtime Python sources"
"$runtime_dir/venv/bin/python" -m compileall -q "$runtime_dir/src"

log_step "Starting $service_name"
systemctl --user start "$service_name"

log_step "Checking backend health"
wait_for_health 10 1

printf "\nEDC runtime sync complete.\n"
printf "Runtime backup: %s\n" "$backup_dir/runtime-pre-sync.tgz"
