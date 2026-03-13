#!/usr/bin/env bash

set -euo pipefail

skip_e2e="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-e2e)
      skip_e2e="true"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: ./scripts/check-all.sh [--skip-e2e]" >&2
      exit 1
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
web_dir="$repo_root/apps/web"
server_dir="$repo_root/apps/server"

require_command() {
  local command_name="$1"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
}

run_step() {
  local step_name="$1"
  shift

  printf '\n==> %s\n' "$step_name"
  "$@"
}

run_server_step() {
  local step_name="$1"
  shift

  printf '\n==> %s\n' "$step_name"
  (
    cd "$server_dir"
    "$@"
  )
}

run_without_proxy() {
  env \
    -u HTTP_PROXY \
    -u HTTPS_PROXY \
    -u ALL_PROXY \
    -u NO_PROXY \
    -u http_proxy \
    -u https_proxy \
    -u all_proxy \
    -u no_proxy \
    "$@"
}

require_command pnpm
require_command uv

run_step "Web lint" pnpm --dir "$web_dir" lint
run_step "Web i18n regression" pnpm --dir "$web_dir" test:i18n
run_step "Web build" pnpm --dir "$web_dir" build
run_step "Web unit tests" pnpm --dir "$web_dir" test

if [[ "$skip_e2e" != "true" ]]; then
  # Playwright 本地回归不依赖外网，清掉代理变量可避免 socks5 配置干扰浏览器启动。
  run_step "Web e2e tests" run_without_proxy pnpm --dir "$web_dir" test:e2e
fi

run_server_step "Server test lint" uv run ruff check tests
run_server_step "Server pytest" uv run pytest

printf '\nAll checks passed.\n'
