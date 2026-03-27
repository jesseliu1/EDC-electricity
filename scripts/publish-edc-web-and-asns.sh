#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

web_dir="${EDC_WEB_SOURCE_DIR:-$repo_root/apps/web}"
asns_dir="${ASNS_SOURCE_DIR:-$repo_root/docs/Ref/asns（ai-sensory-nervous-system）ai感知神經系統}"
webroot="${EDC_WEBROOT:-/var/www/edc-electricity}"
asns_service_name="${ASNS_SERVICE_NAME:-asns-host.service}"
edc_public_url="${EDC_PUBLIC_URL:-https://hopeofthepantheon.me/edc/}"
asns_public_url="${ASNS_PUBLIC_URL:-https://hopeofthepantheon.me/asns/}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
new_assets_dir="assets-github-$timestamp"
archive_dir="$webroot/.publish-$timestamp"

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

current_assets_dir() {
  if [[ ! -f "$webroot/index.html" ]]; then
    return 0
  fi

  sed -n 's#.*src="/edc/\([^/]*\)/index-.*#\1#p' "$webroot/index.html" | head -n 1
}

require_command pnpm
require_command npm
require_command cp
require_command mv
require_command mkdir
require_command sed
require_command grep
require_command curl
require_command systemctl

if [[ ! -d "$web_dir" ]]; then
  echo "EDC web source directory not found: $web_dir" >&2
  exit 1
fi

if [[ ! -d "$asns_dir" ]]; then
  echo "ASNS source directory not found: $asns_dir" >&2
  exit 1
fi

log_step "Building EDC web"
pnpm --dir "$web_dir" build

log_step "Publishing EDC web to $webroot"
mkdir -p "$webroot" "$archive_dir"

current_assets="$(current_assets_dir || true)"
if [[ -n "${current_assets:-}" && -e "$webroot/$current_assets" ]]; then
  mv "$webroot/$current_assets" "$archive_dir/$current_assets"
fi

if [[ -f "$webroot/index.html" ]]; then
  mv "$webroot/index.html" "$archive_dir/index.html"
fi

mkdir -p "$webroot/$new_assets_dir"
cp -a "$web_dir/dist/assets/." "$webroot/$new_assets_dir/"
cp "$web_dir/dist/index.html" "$webroot/index.html"
sed -i "s#/edc/assets/#/edc/$new_assets_dir/#g" "$webroot/index.html"

entry_js="$(find "$webroot/$new_assets_dir" -maxdepth 1 -name 'index-*.js' -print -quit)"
if [[ -z "${entry_js:-}" ]]; then
  echo "Failed to find EDC entry script in $webroot/$new_assets_dir." >&2
  exit 1
fi
sed -i \
  -e "s#\"assets/#\"$new_assets_dir/#g" \
  -e "s#'assets/#'$new_assets_dir/#g" \
  "$entry_js"

if [[ -f "$web_dir/dist/vite.svg" ]]; then
  if [[ -e "$webroot/vite.svg" ]]; then
    if [[ -w "$webroot/vite.svg" ]]; then
      cp "$web_dir/dist/vite.svg" "$webroot/vite.svg"
    else
      echo "Skipping vite.svg publish because target file is not writable: $webroot/vite.svg" >&2
    fi
  elif [[ -w "$webroot" ]]; then
    cp "$web_dir/dist/vite.svg" "$webroot/vite.svg"
  else
    echo "Skipping vite.svg publish because target directory is not writable: $webroot" >&2
  fi
fi

if ! grep -q "/edc/$new_assets_dir/" "$webroot/index.html"; then
  echo "Failed to rewrite EDC index.html to the new assets directory." >&2
  exit 1
fi

log_step "Building ASNS with /asns/ base"
(
  cd "$asns_dir"
  VITE_ASNS_BASE_PATH=/asns/ \
  VITE_ASNS_EDC_APP_URL=/edc/ \
  VITE_ASNS_APP_API_BASE=/api \
    npm run build
)

log_step "Restarting $asns_service_name"
systemctl --user daemon-reload
systemctl --user restart "$asns_service_name"

log_step "Checking public EDC URL"
curl --fail --silent --show-error --location --max-time 20 "$edc_public_url" >/dev/null

log_step "Checking public ASNS URL"
curl --fail --silent --show-error --location --max-time 20 "$asns_public_url" >/dev/null

printf "\nEDC publish complete.\n"
printf "New assets directory: %s\n" "$new_assets_dir"
printf "Archived previous publish into: %s\n" "$archive_dir"
